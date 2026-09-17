{{
  config(
    materialized='table',
    unique_key=['series_id', 'observation_date']
  )
}}

/*
    Silver layer: Cleaned and deduplicated macroeconomic indicators

    Grain: One row per (series_id, observation_date)
    Business Key: series_id, observation_date
*/

with bronze_raw as (

    select * from read_parquet('../data/bronze/fred_series_raw/**/*.parquet', hive_partitioning = 1)

),

unnested as (

    select
        series_id,
        cast(ingested_at as timestamp) as ingested_at,
        -- Unnest the observations array (cast JSON to JSON[] for DuckDB)
        unnest(cast(json_extract(raw_payload, '$.observations') as json [])) as observation
    from bronze_raw

),

parsed as (

    select
        series_id,
        cast(json_extract_string(observation, '$.date') as date) as observation_date,
        json_extract_string(observation, '$.value') as value_str,
        ingested_at
    from unnested
    -- FRED uses '.' for missing values
    where json_extract_string(observation, '$.value') != '.'

),

typed as (

    select
        series_id,
        observation_date,
        cast(value_str as decimal(18, 4)) as value,
        ingested_at
    from parsed
    where try_cast(value_str as decimal(18, 4)) is not null

),

deduped as (

    -- Keep most recent ingestion per (series_id, observation_date)
    select
        *,
        row_number() over (
            partition by series_id, observation_date
            order by ingested_at desc
        ) as rn
    from typed

)

select
    series_id,
    observation_date,
    value,
    ingested_at as last_updated_at
from deduped
where rn = 1
