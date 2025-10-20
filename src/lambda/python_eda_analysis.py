import json
import boto3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

s3_client = boto3.client('s3')
athena_client = boto3.client('athena')

BUCKET_NAME = "currency-analytics-ganit-project"

def run_athena_query(query, database='currency_analytics_processed'):
    """Execute Athena query and return results"""
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': f's3://{BUCKET_NAME}/athena-results/'}
    )
    
    query_execution_id = response['QueryExecutionId']
    
    # Wait for query to complete
    while True:
        query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = query_status['QueryExecution']['Status']['State']
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
    
    if status == 'SUCCEEDED':
        # Get results
        result = athena_client.get_query_results(QueryExecutionId=query_execution_id)
        return result
    else:
        raise Exception(f"Query failed with status: {status}")

def athena_to_dataframe(query_result):
    """Convert Athena result to pandas DataFrame"""
    columns = [col['Label'] for col in query_result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    rows = []
    
    for row in query_result['ResultSet']['Rows'][1:]:  # Skip header
        rows.append([field.get('VarCharValue', '') for field in row['Data']])
    
    return pd.DataFrame(rows, columns=columns)

def handle_missing_volatility(df):
    """Handle missing volatility_30d values using forward fill by currency"""
    print(f"Before filling - Empty volatility_30d cells: {df['volatility_30d'].isna().sum()}")
    
    # Sort by currency and date to ensure proper forward filling
    df = df.sort_values(['target_currency', 'trade_date'])
    
    # Forward fill missing volatility values within each currency group
    df['volatility_30d'] = df.groupby('target_currency')['volatility_30d'].fillna(method='ffill')
    
    # For any remaining missing values at the beginning (no previous value to fill from), use 0
    df['volatility_30d'] = df['volatility_30d'].fillna(0)
    
    print(f"After filling - Empty volatility_30d cells: {df['volatility_30d'].isna().sum()}")
    
    return df

def lambda_handler(event, context):
    try:
        print("Starting Python EDA Analysis...")
        
        # Query 1: Get basic data for analysis
        basic_query = """
        SELECT trade_date, target_currency, exchange_rate, daily_return, volatility_30d
        FROM processed_currency_rates 
        WHERE trade_date >= DATE('2023-01-01')
        ORDER BY trade_date, target_currency
        """
        
        print("Running Athena query...")
        result = run_athena_query(basic_query)
        df = athena_to_dataframe(result)
        
        # Convert data types
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df['exchange_rate'] = pd.to_numeric(df['exchange_rate'])
        df['daily_return'] = pd.to_numeric(df['daily_return'])
        df['volatility_30d'] = pd.to_numeric(df['volatility_30d'])
        
        print(f"Data loaded: {len(df)} records, {df['target_currency'].nunique()} currencies")
        print(f"Initial missing volatility_30d values: {df['volatility_30d'].isna().sum()}")
        
        # 🔧 CRITICAL FIX: Handle missing volatility values
        df = handle_missing_volatility(df)
        
        # 1. Comprehensive Statistical Summary
        print("Generating comprehensive statistical analysis...")
        
        # Basic stats
        stats_summary = df.groupby('target_currency').agg({
            'exchange_rate': ['count', 'mean', 'std', 'min', 'max', 'median'],
            'daily_return': ['mean', 'std', 'min', 'max', 'median'],
            'volatility_30d': ['mean', 'max', 'std', 'count']
        }).round(6)
        
        # Flatten column names
        stats_summary.columns = ['_'.join(col).strip() for col in stats_summary.columns.values]
        stats_summary = stats_summary.reset_index()
        
        # Save statistical summary
        stats_csv = stats_summary.to_csv(index=False)
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key='python-eda-outputs/statistical_analysis/currency_stats_summary.csv',
            Body=stats_csv
        )
        
        # 2. Advanced Correlation Analysis
        print("Generating advanced correlation analysis...")
        
        # Pivot for correlation matrix
        returns_pivot = df.pivot_table(
            values='daily_return', 
            index='trade_date', 
            columns='target_currency'
        ).fillna(0)
        
        # Calculate multiple correlation metrics
        correlation_matrix = returns_pivot.corr()
        covariance_matrix = returns_pivot.cov()
        
        # Save correlation matrices
        correlation_csv = correlation_matrix.to_csv()
        covariance_csv = covariance_matrix.to_csv()
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key='python-eda-outputs/correlation_analysis/currency_correlation_matrix.csv',
            Body=correlation_csv
        )
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key='python-eda-outputs/correlation_analysis/currency_covariance_matrix.csv',
            Body=covariance_csv
        )
        
        # 3. Time Series Analysis Data
        print("Generating time series analysis data...")
        
        # Calculate rolling statistics for major currencies
        major_currencies = ['USD', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF']
        ts_analysis_data = []
        
        for currency in major_currencies:
            if currency in df['target_currency'].values:
                currency_data = df[df['target_currency'] == currency].sort_values('trade_date')
                
                # Calculate rolling metrics
                currency_data = currency_data.copy()
                currency_data['rolling_mean_7d'] = currency_data['exchange_rate'].rolling(window=7).mean()
                currency_data['rolling_std_7d'] = currency_data['exchange_rate'].rolling(window=7).std()
                currency_data['rolling_mean_30d'] = currency_data['exchange_rate'].rolling(window=30).mean()
                currency_data['rolling_volatility_30d'] = currency_data['volatility_30d'].rolling(window=7).mean()
                
                # Add to collection
                for _, row in currency_data.iterrows():
                    ts_analysis_data.append({
                        'trade_date': row['trade_date'],
                        'currency': currency,
                        'exchange_rate': row['exchange_rate'],
                        'rolling_mean_7d': row.get('rolling_mean_7d', None),
                        'rolling_std_7d': row.get('rolling_std_7d', None),
                        'rolling_mean_30d': row.get('rolling_mean_30d', None),
                        'rolling_volatility_30d': row.get('rolling_volatility_30d', None),
                        'daily_return': row['daily_return'],
                        'volatility_30d': row['volatility_30d']
                    })
        
        # Save time series analysis data
        if ts_analysis_data:
            ts_df = pd.DataFrame(ts_analysis_data)
            ts_csv = ts_df.to_csv(index=False)
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key='python-eda-outputs/time_series_analysis/currency_rolling_stats.csv',
                Body=ts_csv
            )
        
        # 4. Volatility Analysis (Now with complete data)
        print("Generating volatility analysis...")
        
        volatility_analysis = df.groupby('target_currency').agg({
            'volatility_30d': ['mean', 'max', 'std', 'count'],
            'daily_return': ['std', 'mean', 'min', 'max']
        }).round(6)
        
        volatility_analysis.columns = ['_'.join(col).strip() for col in volatility_analysis.columns.values]
        volatility_analysis = volatility_analysis.reset_index()
        volatility_analysis = volatility_analysis.rename(columns={
            'volatility_30d_mean': 'avg_volatility',
            'volatility_30d_max': 'max_volatility',
            'volatility_30d_std': 'volatility_std',
            'daily_return_std': 'return_volatility'
        })
        
        # Sort by volatility and save
        volatility_analysis = volatility_analysis.sort_values('avg_volatility', ascending=False)
        volatility_csv = volatility_analysis.to_csv(index=False)
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key='python-eda-outputs/volatility_analysis/currency_volatility_ranking.csv',
            Body=volatility_csv
        )
        
        # 5. Performance Metrics
        print("Generating performance metrics...")
        
        performance_data = []
        for currency in df['target_currency'].unique():
            currency_data = df[df['target_currency'] == currency].sort_values('trade_date')
            if len(currency_data) > 1:
                first_rate = currency_data['exchange_rate'].iloc[0]
                last_rate = currency_data['exchange_rate'].iloc[-1]
                total_return = ((last_rate - first_rate) / first_rate) * 100
                
                performance_data.append({
                    'currency': currency,
                    'total_return_percent': round(total_return, 4),
                    'start_rate': first_rate,
                    'end_rate': last_rate,
                    'total_days': len(currency_data),
                    'avg_daily_return': currency_data['daily_return'].mean(),
                    'avg_volatility': currency_data['volatility_30d'].mean(),
                    'sharpe_ratio': currency_data['daily_return'].mean() / currency_data['daily_return'].std() if currency_data['daily_return'].std() > 0 else 0
                })
        
        performance_df = pd.DataFrame(performance_data)
        performance_csv = performance_df.to_csv(index=False)
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key='python-eda-outputs/performance_analysis/currency_performance_metrics.csv',
            Body=performance_csv
        )
        
        # 6. SIMPLE FORECASTING 
        print("Generating simple forecasts...")

        # Simple forecasting for multiple currencies
        forecast_currencies = ['USD', 'INR', 'AUD', 'GBP', 'SGD', 'JPY']
        forecast_data = []

        for currency in forecast_currencies:
            currency_data = df[df['target_currency'] == currency].sort_values('trade_date')
            if len(currency_data) > 30:
                # Simple moving average forecast
                last_7day_avg = currency_data['exchange_rate'].tail(7).mean()
                last_30day_avg = currency_data['exchange_rate'].tail(30).mean()
                current_rate = currency_data['exchange_rate'].iloc[-1]
        
                # Simple weighted forecast (70% current + 30% trend)
                forecast_rate = round((current_rate * 0.7) + (last_7day_avg * 0.3), 6)
        
                forecast_data.append({
                    'currency': currency,
                    'forecast_date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                    'predicted_rate': forecast_rate,
                    'current_rate': current_rate,
                    '7_day_average': round(last_7day_avg, 6),
                    '30_day_average': round(last_30day_avg, 6),
                    'forecast_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                print(f"✅ Simple forecast generated for {currency}")

        # Save all forecasts
        if forecast_data:
            forecast_df = pd.DataFrame(forecast_data)
            forecast_csv = forecast_df.to_csv(index=False)
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key='python-eda-outputs/forecasting/currency_tomorrow_forecasts.csv',
                Body=forecast_csv
            )
            print(f"✅ Simple forecasts generated for {len(forecast_data)} currencies")

        # 7. Generate Comprehensive EDA Report
        print("Generating comprehensive EDA report...")
        
        report_content = f"""
        COMPREHENSIVE CURRENCY DATA EDA REPORT
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        DATA QUALITY & PREPROCESSING:
        - Total records: {len(df):,}
        - Unique currencies: {df['target_currency'].nunique()}
        - Date range: {df['trade_date'].min()} to {df['trade_date'].max()}
        - Trading days: {df['trade_date'].nunique()}
        - Missing volatility values handled: ✅ Forward Fill (FFill) applied
        - Data completeness: 100% (all missing volatility values filled)
        
        KEY STATISTICAL INSIGHTS:
        - Average exchange rate: {df['exchange_rate'].mean():.6f}
        - Average daily return: {df['daily_return'].mean():.6f}%
        - Average 30-day volatility: {df['volatility_30d'].mean():.6f}
        - Most volatile currency: {volatility_analysis.iloc[0]['target_currency'] if not volatility_analysis.empty else 'N/A'}
        - Best performing currency: {performance_df.loc[performance_df['total_return_percent'].idxmax(), 'currency'] if not performance_df.empty else 'N/A'}
        
        DATA PROCESSING APPLIED:
        ✅ Forward fill (ffill) for missing volatility_30d values
        ✅ Grouped by currency to maintain temporal relationships
        ✅ Zero-fill for initial records with no previous volatility data
        ✅ Complete dataset with no missing values
        
        FILES GENERATED:
        - statistical_analysis/currency_stats_summary.csv (Basic statistics for all currencies)
        - correlation_analysis/currency_correlation_matrix.csv (Currency return correlations)
        - correlation_analysis/currency_covariance_matrix.csv (Currency return covariances)
        - time_series_analysis/currency_rolling_stats.csv (Rolling averages for major currencies)
        - volatility_analysis/currency_volatility_ranking.csv (Volatility rankings)
        - performance_analysis/currency_performance_metrics.csv (Performance metrics & Sharpe ratios)
        
        ANALYSIS COMPLETED:
        ✅ Data quality preprocessing (missing value handling)
        ✅ Descriptive statistics for all currencies
        ✅ Correlation and covariance analysis
        ✅ Time series rolling averages (7-day, 30-day)
        ✅ Volatility ranking and analysis
        ✅ Performance metrics with Sharpe ratios
        ✅ Total return calculations
        
        NEXT STEPS FOR TABLEAU:
        1. Connect Tableau to these CSV files for visualization
        2. Create correlation heatmaps using currency_correlation_matrix.csv
        3. Build volatility dashboards using currency_volatility_ranking.csv
        4. Develop performance tracking using currency_performance_metrics.csv
        5. Implement time series analysis using currency_rolling_stats.csv
        
        NOTE: All missing volatility values have been properly handled using forward fill method.
        """
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key='python-eda-outputs/reports/comprehensive_eda_report.txt',
            Body=report_content
        )
        
        print("Python EDA completed successfully!")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Comprehensive Python EDA completed successfully',
                'data_quality': {
                    'missing_volatility_filled': 'Yes (Forward Fill)',
                    'final_missing_values': 0,
                    'data_completeness': '100%'
                },
                'files_generated': [
                    'currency_stats_summary.csv',
                    'currency_correlation_matrix.csv',
                    'currency_covariance_matrix.csv',
                    'currency_rolling_stats.csv',
                    'currency_volatility_ranking.csv',
                    'currency_performance_metrics.csv',
                    'comprehensive_eda_report.txt'
                ],
                'analysis_completed': [
                    'Missing value handling (Forward Fill)',
                    'Descriptive statistics',
                    'Correlation analysis', 
                    'Covariance analysis',
                    'Time series rolling averages',
                    'Volatility ranking',
                    'Performance metrics',
                    'Sharpe ratio calculation'
                ],
                'records_analyzed': len(df),
                'currencies_analyzed': df['target_currency'].nunique(),
                'date_range': f"{df['trade_date'].min()} to {df['trade_date'].max()}"
            })
        }
        
    except Exception as e:
        error_msg = f"Error in Python EDA: {str(e)}"
        print(error_msg)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': error_msg})
        }