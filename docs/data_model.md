# MarketFeed Lakehouse — Data Model Documentation

## Overview

This lakehouse implements a three-layer medallion architecture optimized for incremental loading, historical accuracy, and analytical consumption.

## Design Principles

1. **Bronze = Immutable Truth:** Raw API responses, never transformed
2. **Silver = Clean Foundation:** Typed, deduplicated, conformed
3. **Gold = Business Value:** Aggregated, denormalized, optimized for consumption

---

## Bronze Layer

### Partitioning Strategy
All bronze tables are partitioned by `ingest_date` (not trade date) to preserve auditability. This allows us to know *when* we pulled data even if the source API backfills or corrects values.

### daily_prices_raw

**Purpose:** Raw stock price API responses from Alpha Vantage

**Schema:**
```
ticker: STRING           -- Stock symbol
raw_payload: JSON        -- Complete API response
ingested_at: TIMESTAMP   -- UTC ingest timestamp
source: STRING           -- 'alpha_vantage'
api_function: STRING     -- API endpoint used
```

**Partitioning:** `ingest_date=YYYY-MM-DD` (derived from ingested_at)

**Grain:** One row per API call (typically one per ticker per day)

**Storage Format:** Parquet with Hive-style partitioning

### fred_series_raw

**Purpose:** Raw macroeconomic indicator data from FRED

**Schema:**
```
series_id: STRING        -- FRED series identifier (e.g., 'CPIAUCSL')
raw_payload: JSON        -- Complete API response with observations array
ingested_at: TIMESTAMP   -- UTC ingest timestamp
source: STRING           -- 'fred'
```

**Partitioning:** `ingest_date=YYYY-MM-DD`

**Grain:** One row per API call (one per series per day)

---

## Silver Layer

### Deduplication Strategy
Bronze intentionally contains overlapping data (Alpha Vantage returns last 100 days on every call). Silver deduplicates via window functions, keeping the most recent ingestion per business key.

### stg_stock_prices

**Purpose:** Cleaned, typed, deduplicated stock prices

**Business Key:** `(ticker, trade_date)`

**Schema:**
```
ticker: STRING
trade_date: DATE
open_price: DECIMAL(18,4)
high_price: DECIMAL(18,4)
low_price: DECIMAL(18,4)
close_price: DECIMAL(18,4)
volume: BIGINT
last_updated_at: TIMESTAMP
```

**Grain:** One row per (ticker, trade_date)

**Transformations:**
- JSON parsing from nested `Time Series (Daily)` structure
- Type coercion to decimal/bigint
- Deduplication via `row_number() over (partition by ticker, trade_date order by ingested_at desc)`

**Tests:**
- `not_null` on all price columns
- Unique combination of (ticker, trade_date)

### stg_macro_indicators

**Purpose:** Cleaned macroeconomic indicators

**Business Key:** `(series_id, observation_date)`

**Schema:**
```
series_id: STRING
observation_date: DATE
value: DECIMAL(18,4)
last_updated_at: TIMESTAMP
```

**Grain:** One row per (series_id, observation_date)

**Transformations:**
- Unnest observations array from raw JSON
- Filter out FRED's `.` missing value sentinel
- Type coercion
- Deduplication

### dim_company (SCD Type 2)

**Purpose:** Slowly changing company metadata with full history

**Business Key:** `ticker`

**Schema:**
```
ticker: STRING
company_name: STRING
sector: STRING
exchange: STRING
effective_date: DATE
valid_from: TIMESTAMP      -- When this version became effective
valid_to: TIMESTAMP        -- When superseded (NULL for current)
is_current: BOOLEAN        -- Convenience flag for current records
```

**Grain:** One row per (ticker, valid_from) — multiple rows per ticker track history

**SCD Strategy:** dbt snapshot with `check` strategy on [company_name, sector, exchange]

**Implementation:**
- dbt automatically manages validity windows
- New records have `valid_to = NULL`
- Historical records have closed `valid_to`
- Enables point-in-time-correct downstream joins

---

## Gold Layer

### daily_price_summary

**Purpose:** Stock prices enriched with technical indicators

**Grain:** One row per (ticker, trade_date)

**Schema:**
```
ticker, trade_date, open_price, high_price, low_price, close_price, volume
ma_7d: DECIMAL(18,4)           -- 7-day moving average
ma_30d: DECIMAL(18,4)          -- 30-day moving average
volatility_30d: DECIMAL(18,4)  -- 30-day rolling std dev
daily_change: DECIMAL(18,4)    -- Absolute price change
daily_return_pct: DECIMAL(18,4) -- Percentage return
```

**Window Functions:**
- Moving averages: `avg(close_price) over (partition by ticker order by trade_date rows between N preceding and current row)`
- Volatility: `stddev(close_price) over (...)`
- Returns: `lag(close_price) over (partition by ticker order by trade_date)`

### sector_performance

**Purpose:** Aggregated daily performance by market sector

**Grain:** One row per (trade_date, sector)

**Schema:**
```
trade_date: DATE
sector: STRING
num_companies: INTEGER
avg_daily_return_pct: DECIMAL(18,4)
total_volume: BIGINT
avg_close_price: DECIMAL(18,4)
min_close_price: DECIMAL(18,4)
max_close_price: DECIMAL(18,4)
```

**Key Join Pattern — Point-in-Time Correctness:**
```sql
from daily_price_summary p
inner join dim_company c
    on p.ticker = c.ticker
    and p.trade_date >= cast(c.valid_from as date)
    and p.trade_date < cast(c.valid_to as date)
```

This ensures historical prices join against the sector classification that was actually true on that date, avoiding anachronistic joins.

### macro_market_correlation

**Purpose:** Market returns with macroeconomic context

**Grain:** One row per trade_date

**Schema:**
```
trade_date: DATE
market_avg_return: DECIMAL(18,4)    -- Average return across all tickers
market_total_volume: BIGINT         -- Total market volume
num_tickers: INTEGER                -- Ticker count
fed_funds_rate: DECIMAL(18,4)       -- As-of join
cpi: DECIMAL(18,4)                  -- As-of join
unemployment_rate: DECIMAL(18,4)    -- As-of join
gdp: DECIMAL(18,4)                  -- As-of join
macro_observation_date: DATE        -- Date of macro snapshot used
```

**Key Join Pattern — As-Of Join:**
```sql
left join macro mc
    on mc.observation_date = (
        select max(observation_date)
        from macro
        where observation_date <= m.trade_date
    )
```

Macro indicators are monthly/quarterly, but market data is daily. The as-of join matches each daily record to the most recent prior macro observation, preventing null rows for dates between macro releases.

---

## Data Quality Strategy

### dbt Tests (Column-Level)
- `not_null` on key business columns
- `unique_combination_of_columns` on business keys
- Custom accepted_values tests on categorical columns

### Great Expectations (Table-Level)
- Freshness checks: bronze data not stale >3 days
- Volume checks: reasonable ticker count per day
- Sanity checks: no negative prices

### Quality Gates
Airflow DAG structure ensures quality checks block downstream:
```
bronze_ingestion → quality_gate → [BLOCK if fail] → dbt_transform
```

---

## Future Enhancements

1. **Incremental dbt Models:** Convert silver to incremental materialization with merge keys
2. **Partition Pruning:** Add date-based partitioning to silver/gold for query performance
3. **Lineage Tracking:** Implement dbt exposures to document downstream BI consumption
4. **Real-Time Layer:** Add streaming ingestion for intraday data
5. **Data Catalog:** Integrate with DataHub or Amundsen for discoverability
