{{
  config(
    materialized='table'
  )
}}

/*
    Gold layer: Sector performance aggregated by day

    Grain: One row per (trade_date, sector)

    Key feature: Point-in-time-correct join with SCD Type 2 dimension
    This ensures we use the sector classification that was actually true
    on each historical date, not today's classification.
*/

with prices as (

    select * from {{ ref('daily_price_summary') }}

),

company as (

    -- SCD Type 2 dimension with validity windows
    select * from {{ ref('dim_company') }}

),

joined as (

    select
        p.trade_date,
        c.sector,
        p.ticker,
        p.close_price,
        p.daily_return_pct,
        p.volume
    from prices as p
    inner join company as c
        -- Point-in-time join: match trade_date against SCD2 validity window
        on
            p.ticker = c.ticker
            and p.trade_date >= cast(c.valid_from as date)
            and p.trade_date < cast(c.valid_to as date)

)

select
    trade_date,
    sector,
    count(distinct ticker) as num_companies,
    avg(daily_return_pct) as avg_daily_return_pct,
    sum(volume) as total_volume,
    avg(close_price) as avg_close_price,
    min(close_price) as min_close_price,
    max(close_price) as max_close_price
from joined
group by trade_date, sector
order by trade_date desc, sector asc
