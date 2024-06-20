#!/usr/bin/env python3
import os

import aws_cdk as cdk

from ec2_vertical_scaling_framework.ec2_vertical_scaling_framework_stack import Ec2VerticalScalingFrameworkStack


app = cdk.App()
Ec2VerticalScalingFrameworkStack(app, "Ec2VerticalScalingFrameworkStack",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()
