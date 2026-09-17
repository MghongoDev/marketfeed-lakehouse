{{
  config(
    materialized='table',
    unique_key=['ticker', 'trade_date']
  )
}}

/*
    Silver layer: Cleaned and deduplicated stock prices

    Grain: One row per (ticker, trade_date)
    Business Key: ticker, trade_date

    Design decisions:
    - Land everything in bronze, dedupe here via window function
    - Keep most recent ingestion per (ticker, date) to handle API backfills/corrections
    - Parse JSON in SQL rather than in ingestion for auditability
*/

/*
    Bronze raw_payload is stored as a native Parquet STRUCT (pandas serializes the
    API dict), so it must be stringified to proper JSON before the JSONPath extraction
    below can work. We also read each ingest_date partition independently and union them,
    because different ingestion days carry slightly different "Time Series (Daily)" keys,
    which DuckDB cannot cast between when globbing the whole tree in one pass.
*/
{%- set partitions = get_bronze_partitions('../data/bronze/daily_prices_raw/**/*.parquet') -%}

with bronze_raw as (

    {%- for partition in partitions %}
        {%- if not loop.first %}    union all
        {%- endif %}
        select
            ticker,
            to_json(raw_payload) as raw_payload,
            ingested_at
        from
            read_parquet(
                '../data/bronze/daily_prices_raw/ingest_date={{ partition }}/**/*.parquet', hive_partitioning = 1
            )
    {%- endfor %}

),

unnested as (

    select
        ticker,
        ingested_at,
        raw_payload,
        -- Unnest the date keys from the nested JSON structure
        unnest(json_keys(json_extract(raw_payload, '$."Time Series (Daily)"'))) as trade_date_str
    from bronze_raw

),

parsed as (

    select
        ticker,
        cast(trade_date_str as date) as trade_date,
        cast(json_extract_string(
            json_extract(
                json_extract(raw_payload, '$."Time Series (Daily)"'),
                '$."' || trade_date_str || '"'
            ),
            '$."1. open"'
        ) as decimal(18, 4)) as open_price,
        cast(json_extract_string(
            json_extract(
                json_extract(raw_payload, '$."Time Series (Daily)"'),
                '$."' || trade_date_str || '"'
            ),
            '$."2. high"'
        ) as decimal(18, 4)) as high_price,
        cast(json_extract_string(
            json_extract(
                json_extract(raw_payload, '$."Time Series (Daily)"'),
                '$."' || trade_date_str || '"'
            ),
            '$."3. low"'
        ) as decimal(18, 4)) as low_price,
        cast(json_extract_string(
            json_extract(
                json_extract(raw_payload, '$."Time Series (Daily)"'),
                '$."' || trade_date_str || '"'
            ),
            '$."4. close"'
        ) as decimal(18, 4)) as close_price,
        cast(json_extract_string(
            json_extract(
                json_extract(raw_payload, '$."Time Series (Daily)"'),
                '$."' || trade_date_str || '"'
            ),
            '$."5. volume"'
        ) as bigint) as volume,
        cast(ingested_at as timestamp) as ingested_at
    from unnested

),

deduped as (

    -- Keep only the most recently ingested value per (ticker, trade_date)
    -- This handles the case where Alpha Vantage returns overlapping data across days
    select
        *,
        row_number() over (
            partition by ticker, trade_date
            order by ingested_at desc
        ) as rn
    from parsed

)

select
    ticker,
    trade_date,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    ingested_at as last_updated_at
from deduped
where rn = 1
