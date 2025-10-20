-- 1) Basic Data Overview
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT target_currency) as unique_currencies,
    MIN(trade_date) as earliest_date,
    MAX(trade_date) as latest_date,
    AVG(exchange_rate) as avg_exchange_rate
FROM currency_analytics_processed.processed_currency_rates;

-- 2) Top 10 Most Volatile Currencies
SELECT 
    target_currency,
    AVG(volatility_30d) as avg_volatility,
    MAX(daily_return) as max_daily_gain,
    MIN(daily_return) as max_daily_loss
FROM currency_analytics_processed.processed_currency_rates
WHERE volatility_30d IS NOT NULL
GROUP BY target_currency
ORDER BY avg_volatility DESC
LIMIT 10;

-- 3) Monthly Performance Analysis
SELECT 
    year,
    month,
    target_currency,
    AVG(exchange_rate) as avg_rate,
    AVG(daily_return) as avg_daily_return,
    AVG(volatility_30d) as avg_volatility
FROM currency_analytics_processed.processed_currency_rates
GROUP BY year, month, target_currency
ORDER BY year, month, target_currency;

-- 4) Day of Week Analysis
SELECT 
    day_of_week,
    AVG(daily_return) as avg_return,
    AVG(volatility_30d) as avg_volatility,
    COUNT(*) as trading_days
FROM currency_analytics_processed.processed_currency_rates
GROUP BY day_of_week
ORDER BY 
    CASE day_of_week
        WHEN 'Mon' THEN 1
        WHEN 'Tue' THEN 2
        WHEN 'Wed' THEN 3
        WHEN 'Thu' THEN 4
        WHEN 'Fri' THEN 5
        WHEN 'Sat' THEN 6
        WHEN 'Sun' THEN 7
    END;

-- 5) Regional Currency Correlations
WITH regional_groups AS (
    SELECT 
        trade_date,
        target_currency,
        daily_return,
        CASE 
            WHEN target_currency IN ('USD', 'CAD', 'MXN') THEN 'NORTH_AMERICA'
            WHEN target_currency IN ('EUR', 'GBP', 'CHF', 'SEK', 'NOK') THEN 'EUROPE'
            WHEN target_currency IN ('JPY', 'CNY', 'KRW', 'SGD') THEN 'ASIA_PACIFIC'
            WHEN target_currency IN ('AUD', 'NZD') THEN 'OCEANIA'
            WHEN target_currency IN ('BRL', 'ARS', 'CLP') THEN 'LATIN_AMERICA'
            ELSE 'OTHER'
        END as currency_region
    FROM currency_analytics_processed.processed_currency_rates
    WHERE target_currency != 'EUR'  -- Base currency
)
SELECT 
    a.currency_region as region1,
    b.currency_region as region2,
    CORR(a.daily_return, b.daily_return) as inter_region_correlation,
    COUNT(*) as overlapping_days
FROM regional_groups a
JOIN regional_groups b 
    ON a.trade_date = b.trade_date 
    AND a.target_currency != b.target_currency
    AND a.currency_region < b.currency_region
GROUP BY a.currency_region, b.currency_region
ORDER BY ABS(inter_region_correlation) DESC;

-- 6) Currency Groups by Correlation Strength
WITH correlations AS (
	SELECT a.target_currency as currency1,
		b.target_currency as currency2,
		CORR(a.daily_return, b.daily_return) as correlation,
		COUNT(*) as overlapping_days
	FROM currency_analytics_processed.processed_currency_rates a
		JOIN currency_analytics_processed.processed_currency_rates b ON a.trade_date = b.trade_date
		AND a.target_currency < b.target_currency
	GROUP BY a.target_currency,
		b.target_currency
	HAVING COUNT(*) > 50
)
SELECT currency1,
	currency2,
	ROUND(correlation, 4) as correlation,
	overlapping_days,
	CASE
		WHEN correlation > 0.8 THEN 'VERY_STRONG_POSITIVE'
		WHEN correlation > 0.6 THEN 'STRONG_POSITIVE'
		WHEN correlation > 0.4 THEN 'MODERATE_POSITIVE'
		WHEN correlation > 0.2 THEN 'WEAK_POSITIVE'
		WHEN correlation > -0.2 THEN 'NEUTRAL'
		WHEN correlation > -0.4 THEN 'WEAK_NEGATIVE'
		WHEN correlation > -0.6 THEN 'MODERATE_NEGATIVE'
		WHEN correlation > -0.8 THEN 'STRONG_NEGATIVE' ELSE 'VERY_STRONG_NEGATIVE'
	END as correlation_strength
FROM correlations
WHERE ABS(correlation) > 0.3 -- Only show meaningful correlations
ORDER BY ABS(correlation) DESC;

-- 7) Regional & Emerging Market Analysis
WITH currency_regions AS (
    SELECT 
        target_currency,
        CASE 
            -- Major Developed
            WHEN target_currency IN ('USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD') THEN 'MAJOR_DEVELOPED'
            -- Scandinavian
            WHEN target_currency IN ('SEK', 'NOK', 'DKK') THEN 'SCANDINAVIAN'
            -- Asian Developed
            WHEN target_currency IN ('SGD', 'HKD', 'KRW') THEN 'ASIAN_DEVELOPED'
            -- Emerging Markets
            WHEN target_currency IN ('CNY', 'INR', 'BRL', 'RUB', 'ZAR', 'MXN', 'TRY') THEN 'EMERGING_MARKETS'
            -- Eastern European
            WHEN target_currency IN ('PLN', 'HUF', 'CZK', 'RON') THEN 'EASTERN_EUROPE'
            -- Other
            ELSE 'OTHER'
        END as currency_group
    FROM currency_analytics_processed.processed_currency_rates
    GROUP BY target_currency
)
SELECT 
    a.currency_group as group1,
    b.currency_group as group2,
    ROUND(CORR(x.daily_return, y.daily_return), 4) as inter_group_correlation,
    COUNT(*) as overlapping_pairs
FROM currency_regions a
JOIN currency_regions b ON a.currency_group <= b.currency_group
JOIN currency_analytics_processed.processed_currency_rates x ON a.target_currency = x.target_currency
JOIN currency_analytics_processed.processed_currency_rates y ON b.target_currency = y.target_currency
    AND x.trade_date = y.trade_date
    AND x.target_currency != y.target_currency
GROUP BY a.currency_group, b.currency_group
ORDER BY a.currency_group, b.currency_group;