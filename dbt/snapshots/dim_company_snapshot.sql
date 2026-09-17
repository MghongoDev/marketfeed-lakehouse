{% snapshot dim_company_snapshot %}

{{
    config(
      target_schema='main',
      unique_key='ticker',
      strategy='check',
      check_cols=['company_name', 'sector', 'exchange'],
    )
}}

/*
    SCD Type 2 snapshot of company metadata

    This tracks slowly changing dimensions over time. When sector, company_name,
    or exchange changes, dbt automatically:
    - Closes the old record (sets dbt_valid_to)
    - Opens a new record (sets dbt_valid_from, dbt_valid_to=NULL)

    This enables point-in-time-correct joins downstream.
*/

select
    ticker,
    company_name,
    sector,
    exchange,
    effective_date
from {{ ref('company_metadata') }}

{% endsnapshot %}
