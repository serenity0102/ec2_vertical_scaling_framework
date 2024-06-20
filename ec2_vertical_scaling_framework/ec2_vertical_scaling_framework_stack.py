from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_cloudwatch,
    aws_events as events,
    aws_events_targets as targets,
    aws_apigateway as apigateway,
    aws_scheduler as scheduler,
    Duration,
)
from constructs import Construct


class Ec2VerticalScalingFrameworkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # get context
        sns_topic_arn = self.node.try_get_context("sns_topic_arn")
        resize_time_zone = self.node.try_get_context("resize_time_zone")
        instance_id = self.node.try_get_context("instance_id")
        cpu_threshold_upsize = self.node.try_get_context("cpu_threshold_upsize")
        mem_threshold_upsize = self.node.try_get_context("mem_threshold_upsize")
        cpu_threshold_downsize = self.node.try_get_context("cpu_threshold_downsize")
        mem_threshold_downsize = self.node.try_get_context("mem_threshold_downsize")

        #
        # create IAM role with trust relationship by Principal scheduler.amazonaws.com with permission CloudWatchFullAccessV2 and AWSLambda_FullAccess
        # this IAM role will be used by the EventBridge Scheduler
        #
        ec2_resize_scheduler_role = iam.Role(
            self, "Ec2ResizeSchedulerRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("scheduler.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccessV2"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSLambda_FullAccess"),
            ],
        )


        #
        # Create the Lambda function EC2Resize to resize the EC2
        #
        # Define the IAM role for the Lambda function
        EC2ResizeRole = iam.Role(
            self, "EC2ResizeLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonSSMAutomationRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSNSFullAccess"),
            ],
        )
        ec2_resize_lambda = lambda_.Function(
            self, "EC2Resize",
            code=lambda_.Code.from_asset("ec2_vertical_scaling_framework/lambda/ec2-resize"),
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="ec2-resize.lambda_handler",
            role=EC2ResizeRole,
            timeout=Duration.seconds(60),
        )

        #
        # Create the Lambda function EC2SchedulerResize
        #
        ec2_scheduler_resize_lambda_role = iam.Role(
            self, "EC2SchedulerResizeRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEventBridgeSchedulerFullAccess"),
            ],
        )
        ec2_scheduler_resize_lambda = lambda_.Function(
            self, "EC2SchedulerResize",
            code=lambda_.Code.from_asset("ec2_vertical_scaling_framework/lambda/ec2-scheduler"),
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="ec2-scheduler-resize.lambda_handler",
            role=ec2_scheduler_resize_lambda_role,
            environment={
                "ec2_resize_lambda_ARN": ec2_resize_lambda.function_arn,
                "sns_topic_arn": sns_topic_arn,
                "scheduler_role_arn": ec2_resize_scheduler_role.role_arn,
                "resize_time_zone": resize_time_zone
            },
            timeout=Duration.seconds(60),
        )

        #
        # Create the API Gateway EC2SchedulerResizeAPI to create a resize scheduler
        #
        policy_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],  # Allow all principals
            actions=["execute-api:Invoke"],
            resources=["execute-api:/*/*/*"],
        )
        policy_document = iam.PolicyDocument(statements=[policy_statement])
        api = apigateway.RestApi(
            self, "EC2SchedulerResizeAPI",
            endpoint_types=[apigateway.EndpointType.PRIVATE],
            deploy_options=apigateway.StageOptions(
                data_trace_enabled=True,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                metrics_enabled=True,
            ),
            policy=policy_document 
        )
        # Define the Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            ec2_scheduler_resize_lambda,
            proxy=False,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    },
                )
            ],
            request_templates={
                "application/json": """
                {
                    "body": {
                        "datetime": "$input.params('datetime')",
                        "instanceId": "$input.params('instanceId')",
                        "targetInstanceType": "$input.params('targetInstanceType')"
                    }
                }
                """
            },
        )
        # Create the API Gateway resource and method
        api_resource = api.root.add_resource("resize")
        method = api_resource.add_method("GET", 
                                lambda_integration,
                                method_responses=[
                                    apigateway.MethodResponse(
                                        status_code="200",
                                        response_parameters={
                                            "method.response.header.Access-Control-Allow-Origin": True
                                        },
                                    )
                                ],)



        #
        # Define the Lambda function EC2VerticalScaleCheck to check whether the EC2 needs vertical scaling
        #
        vertical_scale_check_lambda = lambda_.Function(
            self, "EC2VerticalScaleCheck",
            code=lambda_.Code.from_asset("ec2_vertical_scaling_framework/lambda/ec2-check"),
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="ec2-vertical-scale-check.lambda_handler",
            timeout=Duration.seconds(60),
            environment={
                "instance_id": instance_id,
                "cpu_threshold_upsize": cpu_threshold_upsize,
                "mem_threshold_upsize": mem_threshold_upsize,
                "cpu_threshold_downsize": cpu_threshold_downsize,
                "mem_threshold_downsize": mem_threshold_downsize,
                "sns_topic_arn": sns_topic_arn,
                "ec2_scheduler_url": f"{api.url}resize"
            }
        )
        # Grant necessary permissions to the Lambda function
        vertical_scale_check_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeInstances",
                    "ec2:ModifyInstanceAttribute",
                    "ec2:TerminateInstances",
                ],
                resources=["*"],
            )
        )
        vertical_scale_check_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:GetMetricData",
                    "cloudwatch:GetMetricStatistics",
                    "sns:Publish"
                ],
                resources=["*"],
            )
        )

        #
        # Create a EventBridge Scheduler to run every week to trigger Lambda function EC2VerticalScaleCheck
        #
        ec2_scheduler_weekly = scheduler.CfnSchedule(
            self, "EC2SchedulerWeekly",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(
                mode="OFF",
            ),
            schedule_expression="cron(0 19 ? * 2 *)",
            schedule_expression_timezone = "Asia/Hong_Kong",
            group_name="default",
            target=scheduler.CfnSchedule.TargetProperty(
                arn=vertical_scale_check_lambda.function_arn,
                role_arn=ec2_resize_scheduler_role.role_arn,
                input="{\"instance_id\":\"" + instance_id + 
                "\",\"cpu_threshold_upsize\":\"" + cpu_threshold_upsize + 
                "\",\"mem_threshold_upsize\":\"" + mem_threshold_upsize + 
                "\",\"cpu_threshold_downsize\":\"" + cpu_threshold_downsize + 
                "\",\"mem_threshold_downsize\":\"" + mem_threshold_downsize + 
                "\",\"sns_topic_arn\":\"" + sns_topic_arn + "\"}",
            ),
        )
        # # Define the payload
        # payload = {
        #     "instance_id": instance_id,
        #     "cpu_threshold_upsize": cpu_threshold_upsize,
        #     "mem_threshold_upsize": mem_threshold_upsize,
        #     "cpu_threshold_downsize": cpu_threshold_downsize,
        #     "mem_threshold_downsize": mem_threshold_downsize,
        #     "sns_topic_arn": sns_topic_arn,
        # }