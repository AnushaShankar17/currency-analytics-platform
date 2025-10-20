import json
import boto3
import requests
from datetime import datetime, timedelta
import urllib3

# Disable SSL warnings (optional)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Fetch currency data from Frankfurter API and store in S3
    """
    try:
        # Configuration
        BUCKET_NAME = "currency-analytics-ganit-project"  
        base_url = "https://api.frankfurter.dev/v1/"
        
        # Calculate date range (from 2023 to today)
        start_date = "2023-01-01"
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"Fetching data from {start_date} to {end_date}")
        
        # API call to get all currencies time series
        api_url = f"{base_url}{start_date}..{end_date}"
        
        print(f"API URL: {api_url}")
        
        response = requests.get(api_url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract base information
            base_currency = data.get('base', 'EUR')
            start_date_api = data.get('start_date')
            end_date_api = data.get('end_date')
            rates = data.get('rates', {})
            
            print(f"Retrieved data: {base_currency} from {start_date_api} to {end_date_api}")
            print(f"Total days: {len(rates)}")
            
            # Process and store data by date
            processed_records = []
            for date_str, currency_rates in rates.items():
                for currency, rate in currency_rates.items():
                    record = {
                        'date': date_str,
                        'base_currency': base_currency,
                        'target_currency': currency,
                        'exchange_rate': rate,
                        'year': date_str[:4],
                        'month': date_str[5:7]
                    }
                    processed_records.append(record)
            
            print(f"Processed {len(processed_records)} currency records")
            
            # Store in S3 with partitioning
            if processed_records:
                current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_key = f"raw-data/year={datetime.now().year}/month={datetime.now().strftime('%m')}/currency_data_{current_date}.json"
                
                s3_client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=file_key,
                    Body=json.dumps(processed_records, indent=2),
                    ContentType='application/json'
                )
                
                print(f"Successfully stored data in S3: {file_key}")
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Data ingestion successful',
                        'records_processed': len(processed_records),
                        's3_location': f"s3://{BUCKET_NAME}/{file_key}",
                        'date_range': f"{start_date_api} to {end_date_api}"
                    })
                }
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'No data processed'})
                }
                
        else:
            error_msg = f"API request failed with status {response.status_code}"
            print(error_msg)
            return {
                'statusCode': response.status_code,
                'body': json.dumps({'error': error_msg})
            }
            
    except Exception as e:
        error_msg = f"Error in Lambda function: {str(e)}"
        print(error_msg)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': error_msg})
        }