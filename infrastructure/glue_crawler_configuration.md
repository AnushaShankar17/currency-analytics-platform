# Glue Crawler Configuration

## Crawler Details
- **Name**: currency-raw-data-crawler
- **Description**: Crawls raw currency data from S3 and creates table schema
- **Schedule**: On demand

## Data Source
- **Type**: S3
- **Path**: s3://currency-analytics-ganit-project/raw-data/
- **Recrawl**: Recrawl all data

## Security Settings  
- **IAM Role**: CurrencyAnalyticsGlueRole
- **Security Configuration**: None
- **Lake Formation**: None

## Output Configuration
- **Database**: currency_analytics_db
- **Table Prefix**: raw_
- **Maximum Table Threshold**: Default

## Schema Discovery
The crawler automatically:
- Discovers JSON schema from raw data files
- Creates tables in Glue Data Catalog
- Handles partitioned data (year/month structure)
- Maintains schema evolution as new data arrives
