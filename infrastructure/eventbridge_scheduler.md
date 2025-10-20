# EventBridge Scheduler Configuration

## Schedule Details
- **Name**: DailyCurrencyDataIngestion
- **Description**: Trigger daily currency data fetch at 16:00 CET
- **Schedule Group**: default
- **Time Zone**: (UTC+05:30) Asia/Calcutta
- **Occurrence**: Recurring

## Cron Expression
`0 15 * * ? *`
- **Minutes**: 0
- **Hours**: 15 (3:00 PM)
- **Runs Daily**: At 15:00 UTC (16:00 CET)

## Target Configuration
- **Target Type**: AWS Lambda
- **Function**: CurrencyDataIngestion
- **Target ARN**: arn:aws:lambda:ap-south-1:258993894758:function:CurrencyDataIngestion
- **Payload**: None

## Schedule Settings
- **Schedule State**: Enabled
- **Execution Role**: CurrencyDataSchedulerRole
- **Action after completion**: NONE

## Retry Policy
- **Maximum Retries**: 185
- **Dead-letter Queue**: None

## Next 10 Trigger Dates
- Mon, 20 Oct 2025 15:00:00 (UTC+05:30)
- Tue, 21 Oct 2025 15:00:00 (UTC+05:30)
- Wed, 22 Oct 2025 15:00:00 (UTC+05:30)
- Thu, 23 Oct 2025 15:00:00 (UTC+05:30)
- Fri, 24 Oct 2025 15:00:00 (UTC+05:30)
