{{
  config(
    materialized='table'
  )
}}

/*
    Gold layer: Market-wide returns correlated with macroeconomic indicators

    Grain: One row per trade_date

    This mart answers: "How do market returns correlate with macro conditions?"

    Uses an as-of join pattern: macro data is less frequent than daily prices
    (monthly/quarterly), so we join to the most recent prior macro observation.
*/

with macro as (

    select
        observation_date,
        max(case when series_id = 'FEDFUNDS' then value end) as fed_funds_rate,
        max(case when series_id = 'CPIAUCSL' then value end) as cpi,
        max(case when series_id = 'UNRATE' then value end) as unemployment_rate,
        max(case when series_id = 'GDP' then value end) as gdp
    from {{ ref('stg_macro_indicators') }}
    group by observation_date

),

market as (

    select
        trade_date,
        avg(daily_return_pct) as market_avg_return,
        sum(volume) as market_total_volume,
        count(distinct ticker) as num_tickers
    from {{ ref('daily_price_summary') }}
    group by trade_date

)

select
    m.trade_date,
    m.market_avg_return,
    m.market_total_volume,
    m.num_tickers,
    mc.fed_funds_rate,
    mc.cpi,
    mc.unemployment_rate,
    mc.gdp,
    mc.observation_date as macro_observation_date
from market m
left join macro mc
    -- As-of join: get the most recent macro observation prior to trade_date
    on mc.observation_date = (
        select max(observation_date)
        from macro
        where observation_date <= m.trade_date
    )
order by m.trade_date desc
