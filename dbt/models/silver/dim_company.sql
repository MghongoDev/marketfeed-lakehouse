{{
  config(
    materialized='view'
  )
}}

/*
    Clean interface over the SCD Type 2 snapshot

    Provides:
    - Renamed valid_from/valid_to columns (clearer than dbt_ prefix)
    - is_current flag for current records
    - Uses 9999-12-31 sentinel for open records instead of NULL
*/

select
    ticker,
    company_name,
    sector,
    exchange,
    effective_date,
    dbt_valid_from as valid_from,
    coalesce(dbt_valid_to, timestamp '9999-12-31 23:59:59') as valid_to,
    dbt_valid_to is null as is_current
from {{ ref('dim_company_snapshot') }}
