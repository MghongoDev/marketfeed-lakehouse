{{
  config(
    materialized='table'
  )
}}

/*
    Gold layer: Daily price summary with rolling metrics

    Grain: One row per (ticker, trade_date)

    Adds business metrics:
    - 7-day and 30-day moving averages
    - 30-day volatility (standard deviation)
    - Daily price change and return percentage
*/

with prices as (

    select * from {{ ref('stg_stock_prices') }}

),

with_rolling_metrics as (

    select
        ticker,
        trade_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,

        -- 7-day moving average
        avg(close_price) over (
            partition by ticker
            order by trade_date asc
            rows between 6 preceding and current row
        ) as ma_7d,

        -- 30-day moving average
        avg(close_price) over (
            partition by ticker
            order by trade_date asc
            rows between 29 preceding and current row
        ) as ma_30d,

        -- 30-day volatility (standard deviation)
        stddev(close_price) over (
            partition by ticker
            order by trade_date asc
            rows between 29 preceding and current row
        ) as volatility_30d,

        -- Previous day's close for calculating returns
        lag(close_price) over (
            partition by ticker
            order by trade_date asc
        ) as prev_close

    from prices

)

select
    ticker,
    trade_date,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    ma_7d,
    ma_30d,
    volatility_30d,
    -- Daily change in absolute terms
    close_price - prev_close as daily_change,
    -- Daily return as percentage
    case
        when prev_close is not null and prev_close > 0
        then ((close_price - prev_close) / prev_close) * 100
        else null
    end as daily_return_pct
from with_rolling_metrics
