# IAM Roles Configuration

## 1. CurrencyPythonEDARole
**Purpose**: Role for Currency Python EDA Lambda function to access S3, Athena, and Glue

**ARN**: `arn:aws:iam::258993894758:role/CurrencyPythonEDARole`

**Managed Policies**:
- AmazonAthenaFullAccess
- AmazonS3FullAccess  
- AWSGlueConsoleFullAccess
- CloudWatchLogsFullAccess

## 2. CurrencyDataSchedulerRole  
**Purpose**: Role for EventBridge scheduler to invoke Lambda functions

**ARN**: `arn:aws:iam::258993894758:role/service-role/CurrencyDataSchedulerRole`

**Policies**:
- Amazon-EventBridge-Scheduler-Execution-Policy (Customer managed)
- LambdaInvokePermission (Customer inline)

## 3. CurrencyAnalyticsLambdaRole
**Purpose**: Role for currency data ingestion Lambda function

**ARN**: `arn:aws:iam::258993894758:role/CurrencyAnalyticsLambdaRole`

**Managed Policies**:
- AmazonS3FullAccess
- AWSGlueServiceRole  
- CloudWatchLogsFullAccess

## 4. CurrencyAnalyticsGlueRole
**Purpose**: Role for currency data processing Glue ETL

**ARN**: `arn:aws:iam::258993894758:role/CurrencyAnalyticsGlueRole`

**Managed Policies**:
- AmazonS3FullAccess
- AWSGlueServiceRole

## 5. Amazon_EventBridge_Scheduler_LAMBDA
**Purpose**: System role for EventBridge scheduler

**ARN**: `arn:aws:iam::258993894758:role/service-role/Amazon_EventBridge_Scheduler_LAMBDA_6a04ce4e25`

**Policies**:
- Amazon-EventBridge-Scheduler-Execution-Policy (Customer managed)