import sys
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ['JOB_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

# Configuration
BUCKET_NAME = "currency-analytics-ganit-project"
S3_RAW_PATH = f"s3://{BUCKET_NAME}/raw-data/"
OUTPUT_PATH = f"s3://{BUCKET_NAME}/processed-data/currency_rates/"

try:
    # Read partitioned JSON files
    print("Reading partitioned JSON data from S3...")
    
    raw_df = spark.read.option("basePath", S3_RAW_PATH) \
                      .option("multiLine", "true") \
                      .option("mode", "PERMISSIVE") \
                      .option("columnNameOfCorruptRecord", "_corrupt_record") \
                      .json(f"{S3_RAW_PATH}year=*/month=*/")
    
    print("Raw data schema:")
    raw_df.printSchema()
    print(f"Raw data count: {raw_df.count()}")
    
    # Show sample data
    if raw_df.count() > 0:
        print("Sample raw data:")
        raw_df.select("date", "base_currency", "target_currency", "exchange_rate", "year", "month").show(10, truncate=False)
    
    # Check for corrupt records
    if "_corrupt_record" in raw_df.columns:
        corrupt_count = raw_df.filter(col("_corrupt_record").isNotNull()).count()
        print(f"Corrupt records found: {corrupt_count}")
        if corrupt_count > 0:
            raw_df = raw_df.filter(col("_corrupt_record").isNull())
            print(f"Records after removing corrupt: {raw_df.count()}")
    
    if raw_df.count() == 0:
        raise Exception("No valid data found!")
    
    # FIXED PROCESSING: Keep all fields but correct date logic
    print("Processing data with corrected date logic...")
    
    # Step 1: Create base DataFrame with all original fields
    base_df = raw_df.select(
        col("date").cast("date").alias("trade_date"),
        col("base_currency"),
        col("target_currency"),
        col("exchange_rate").cast("double")
    ).distinct()
    
    # Step 2: Calculate all derived metrics FIRST
    window_spec = Window.partitionBy("target_currency").orderBy("trade_date")
    
    processed_df = base_df.withColumn(
        "prev_day_rate", 
        lag("exchange_rate", 1).over(window_spec)
    ).withColumn(
        "daily_return",
        when(col("prev_day_rate").isNull(), 0)
        .otherwise(((col("exchange_rate") - col("prev_day_rate")) / col("prev_day_rate")) * 100)
    ).drop("prev_day_rate")
    
    # Calculate moving averages
    processed_df = processed_df.withColumn(
        "moving_avg_7d",
        avg("exchange_rate").over(window_spec.rowsBetween(-6, 0))
    ).withColumn(
        "moving_avg_30d", 
        avg("exchange_rate").over(window_spec.rowsBetween(-29, 0))
    )
    
    # Calculate volatility
    processed_df = processed_df.withColumn(
        "volatility_30d",
        stddev("daily_return").over(window_spec.rowsBetween(-29, 0))
    )
    
    # 🔥 FIX: Handle null volatility values
    print(f"Null volatility values before filling: {processed_df.filter(col('volatility_30d').isNull()).count()}")
    
    # Fill null volatility values with 0 (for beginning of series)
    processed_df = processed_df.withColumn(
        "volatility_30d", 
        when(col("volatility_30d").isNull(), 0.0).otherwise(col("volatility_30d"))
    )
    
    print(f"After filling - Null volatility values: {processed_df.filter(col('volatility_30d').isNull()).count()}")
    
    if processed_df.filter(col('volatility_30d').isNull()).count() > 0:
        print("❌ WARNING: Still have null volatility values!")
    else:
        print("✅ SUCCESS: All null volatility values filled!")
    
    # Step 3: Add ALL date fields - EXTRACTED FROM trade_date (not partitions)
    processed_df = processed_df.withColumn(
        "day_of_week", date_format(col("trade_date"), "E")
    ).withColumn(
        "month_name", date_format(col("trade_date"), "MMMM")
    ).withColumn(
        "quarter", quarter(col("trade_date"))
    ).withColumn(
        "year", year(col("trade_date"))  # CORRECTED: From trade_date
    ).withColumn(
        "month", month(col("trade_date"))  # CORRECTED: From trade_date
    )
    
    # Reorder columns to match expected schema
    final_columns = [
        "trade_date", "base_currency", "target_currency", "exchange_rate",
        "daily_return", "moving_avg_7d", "moving_avg_30d", "volatility_30d",
        "day_of_week", "month_name", "quarter", "year", "month"
    ]
    
    processed_df = processed_df.select(final_columns)
    
    print("Final processed data sample:")
    processed_df.show(10, truncate=False)
    
    print("Data verification - checking date consistency:")
    verification_df = processed_df.select(
        "trade_date", "year", "month", "quarter", "month_name"
    ).filter(col("trade_date").between("2022-12-30", "2023-01-05"))
    
    verification_df.show(10, truncate=False)
    
    print(f"Total records: {processed_df.count()}")
    
    # Write to S3
    print("Writing to S3...")
    processed_df.write.mode("overwrite").format("parquet") \
        .partitionBy("year", "month") \
        .option("path", OUTPUT_PATH) \
        .save()
    
    print(f"✅ Data written to: {OUTPUT_PATH}")
    
    # Create Glue table (updated schema)
    print("Creating Glue table...")
    spark.sql("CREATE DATABASE IF NOT EXISTS currency_analytics_processed")
    
    spark.sql(f"""
        CREATE EXTERNAL TABLE IF NOT EXISTS currency_analytics_processed.processed_currency_rates (
            trade_date DATE,
            base_currency STRING,
            target_currency STRING, 
            exchange_rate DOUBLE,
            daily_return DOUBLE,
            moving_avg_7d DOUBLE,
            moving_avg_30d DOUBLE,
            volatility_30d DOUBLE,
            day_of_week STRING,
            month_name STRING,
            quarter INT
        )
        PARTITIONED BY (year INT, month INT)
        STORED AS PARQUET
        LOCATION '{OUTPUT_PATH}'
    """)
    
    spark.sql("MSCK REPAIR TABLE currency_analytics_processed.processed_currency_rates")
    
    print("✅ Glue ETL job completed successfully!")
    
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    import traceback
    print(f"Full error: {traceback.format_exc()}")
    raise e