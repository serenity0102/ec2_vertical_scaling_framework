
# Welcome to EC2 vertical scaling framework

## Prerequisite

We assume that 
* you already install CloudWatch agent on your EC2, so that we could featch the mem_used_percent metric in CloudWatch for scaling decision making. 
* you aleady have an SNS policy to receive notification. Please put the SNS topic ARN into the context.json. For example
* you already have a VPC endpoint for API Gateway in your VPC. 

You should have following parameters in the context in cdk.json file:
    "instance_id": "i-0a12135a00ace182c",
    "cpu_threshold_upsize": "0.9",
    "mem_threshold_upsize": "0.9",
    "cpu_threshold_downsize": "0.4",
    "mem_threshold_downsize": "0.4",
    "sns_topic_arn": "arn:aws:sns:ap-east-1:383386985941:ec2_vscalling_inform",
    "resize_time_zone": "Asia/Shanghai",


## Architecture

You can find the framework architecture as below.
![Architecture](docs/EC2-verticalscaling.png)

The following are the data flow of the EC2 instance auto-scaling solution:

1. Amazon EventBridge: Triggers AWS Lambda functions based on scheduled CPU utilization events, enabling usage tracking and scaling actions.

2. AWS Lambda: Uses the CloudWatch API to retrieve EC2 instance metrics, such as CPU utilization and memory usage. It is triggered based on a specific event and sends notifications to SNS.

3. Amazon SNS: Delivers notifications to users, allowing them to track scaling activities at specific time intervals.

4. Amazon API Gateway and AWS Lambda: API Gateway receives scaling requests, which then invoke AWS Lambda functions to perform scheduled scaling actions.

5. AWS Systems Manager: Used for resize the EC2 instance.

## Key components
Here are the introduction of key components.

### Amazon CloudWatch 
CloudWatch is an excellent monitoring tool for AWS EC2 instances. It allows you to view the CPU utilization for each EC2 instance. If you have installed the CloudWatch Agent on your EC2 instances, you can also publish metrics such as memory and disk utilization to CloudWatch for monitoring. 

Here is an example of monitoring EC2 CPU and memory usage to determine whether to scale resources up or down.

The sentence and table describe an example of monitoring EC2 CPU and memory usage to determine whether to scale resources up or down.

Scaling Metric | Metric Name | Action Logic
--- | --- | ---
CPU Scaling Down | cpuutilization | If the average CPU utilization over a 7-day period is below a certain low threshold, it is considered a candidate for scaling down CPU resources.
Memory Scaling Down | mem_used_percent | If the average memory utilization over a 7-day period is below a certain low threshold, it is considered a candidate for scaling down memory resources.
CPU Scaling Up | cpuutilization | If there are 5 instances within a 7-day period where the CPU utilization exceeds a certain high threshold, it is considered a candidate for scaling up CPU resources.
Memory Scaling Up | mem_used_percent | If there are 5 instances within a 7-day period where the memory utilization exceeds a certain high threshold, it is considered a candidate for scaling up memory resources.

### Amazon EC2 Instance Size
For AWS EC2 instances, different use cases may require different instance families. You can choose from various instance families, such as the general-purpose M series, the compute-optimized C series, and the memory-optimized R series.
• The M series instances have vCPU and memory ratios of 1 vCPU for every 4GB of memory, suitable for general-purpose workloads.
• The C series instances have vCPU and memory ratios of 1 vCPU for every 2GB of memory, suitable for compute-intensive workloads.
• The R series instances have vCPU and memory ratios of 1 vCPU for every 8GB of memory, suitable for memory-intensive applications.
For more details, visit: https://aws.amazon.com/ec2/instance-types/

The following table outlines some guidelines for selecting CPU and memory configurations when there are needs to scale up/down CPU and memory:

CPU/Memory Scaling | Memory Scaling Down | Memory No Change | Memory Scaling Up
--- | --- | --- | ---
CPU Scaling Down | Same series, smaller size | No change for R series; M to R series; C to M series | Larger size for R; M to R series; C to M series
CPU No Change | R to M series; M to C series; No change for C series | Keep current | Larger size for R series; M to R series; C to M series
CPU Scaling Up | R to M series; M to C series; Larger size for C series | R to M series; M to C series; Larger size for C series | Same series, larger size

### API Gateway
For security purpose, we use private API gateway here, so that only your company intranet could trigger the EC2 resize. You need to Create a VPC endpoint for API Gateway in your VPC to access the API gateway. Please refer more: https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-private-api-create.html. 


## Notes

* We only check one EC2 instance in the framework. You can adjust the code to check a group of EC2 instances.

* this is only a prototyping. If you want to make it production, you need to consider the situation such as the resize schedule URL is triggered multiple times with different datetime, how do you avoid resizing duplicately. 


Enjoy!