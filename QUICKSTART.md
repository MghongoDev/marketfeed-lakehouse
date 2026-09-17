# MarketFeed Lakehouse - Quick Start Guide

This guide walks you through running the complete pipeline from scratch.

## Prerequisites

- Python 3.11 or higher
- Git
- Internet connection (for API calls)

## Step 1: Environment Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Verify dependencies are installed
python -c "import pandas, duckdb, requests; print('✓ Core dependencies installed')"
```

## Step 2: Configure API Keys

Your API keys are already set up in `.env`. Verify:

```bash
# Check environment variables load correctly
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('Alpha Vantage Key:', os.getenv('ALPHA_VANTAGE_API_KEY')[:10] + '...')
print('FRED Key:', os.getenv('FRED_API_KEY')[:10] + '...')
"
```

## Step 3: Run Bronze Ingestion

```bash
# Ingest stock prices (takes ~10 seconds due to API rate limits)
python ingestion/alpha_vantage.py

# Ingest macro indicators
python ingestion/fred.py

# Verify data landed correctly
ls -lh data/bronze/daily_prices_raw/ingest_date=*/
ls -lh data/bronze/fred_series_raw/ingest_date=*/
```

## Step 4: Build Silver Layer with dbt

```bash
cd dbt

# Install dbt packages (dbt-utils)
dbt deps

# Load company metadata
dbt seed

# Create SCD Type 2 snapshot
dbt snapshot

# Build and test silver models
dbt run --select silver
dbt test --select silver

# Check results
duckdb ../data/marketfeed.duckdb "SELECT COUNT(*) as row_count FROM stg_stock_prices"
```

## Step 5: Build Gold Layer

```bash
# Still in dbt/ directory

# Build gold marts
dbt run --select gold

# Test gold marts
dbt test --select gold

# Query a gold table
duckdb ../data/marketfeed.duckdb "
SELECT
    ticker,
    trade_date,
    close_price,
    ma_7d,
    daily_return_pct
FROM daily_price_summary
ORDER BY trade_date DESC, ticker
LIMIT 10
"
```

## Step 6: Run Data Quality Checks

```bash
cd ..  # Back to project root

python great_expectations/checks/freshness_check.py
```

## Step 7: Generate Documentation

```bash
cd dbt

dbt docs generate
dbt docs serve --port 8081
```

Open http://localhost:8081 in your browser to explore:
- Interactive lineage graph
- Model documentation
- Column descriptions
- Test results

## Step 8: Run Unit Tests

```bash
cd ..  # Back to project root

PYTHONPATH=. pytest tests/ -v
```

Expected output: `9 passed`

## Querying the Data

### Example: Daily Price Summary
```sql
SELECT
    ticker,
    trade_date,
    close_price,
    ma_7d,
    ma_30d,
    volatility_30d,
    daily_return_pct
FROM daily_price_summary
WHERE ticker = 'AAPL'
ORDER BY trade_date DESC
LIMIT 10;
```

### Example: Sector Performance
```sql
SELECT
    trade_date,
    sector,
    num_companies,
    avg_daily_return_pct,
    total_volume
FROM sector_performance
ORDER BY trade_date DESC, avg_daily_return_pct DESC;
```

### Example: Macro Correlation
```sql
SELECT
    trade_date,
    market_avg_return,
    fed_funds_rate,
    unemployment_rate,
    cpi
FROM macro_market_correlation
ORDER BY trade_date DESC
LIMIT 10;
```

### Example: SCD Type 2 History
```sql
-- Show company history with validity windows
SELECT
    ticker,
    company_name,
    sector,
    valid_from,
    valid_to,
    is_current
FROM dim_company
WHERE ticker = 'AAPL'
ORDER BY valid_from;
```

## Troubleshooting

### "API rate limit exceeded"
Wait 24 hours or reduce the ticker list in `ingestion/alpha_vantage.py`

### "No bronze data found"
Run the ingestion scripts first (Step 3)

### "Database not found"
Run `dbt run` to create the DuckDB database

### "Module not found"
Activate venv: `source venv/bin/activate`

## Next Steps

1. **Modify the ticker list** in `ingestion/alpha_vantage.py` to track different stocks
2. **Add a new gold mart** by creating a new `.sql` file in `dbt/models/gold/`
3. **Test SCD Type 2** by editing `dbt/seeds/company_metadata.csv` and running `dbt seed` + `dbt snapshot`
4. **Set up Airflow** to run the pipeline on a schedule
5. **Deploy to the cloud** by migrating from DuckDB to Snowflake

## Learning Path

1. ✅ Run the pipeline end-to-end (this guide)
2. Read `docs/data_model.md` to understand the design
3. Explore dbt documentation at http://localhost:8081
4. Review `BUILD_STATUS.md` for interview talking points
5. Try modifying models and re-running dbt

---

**Estimated time to complete:** 15-20 minutes

**Data freshness:** Your bronze data contains real market data as of today (2026-09-17)
