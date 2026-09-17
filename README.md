# MarketFeed Lakehouse

A production-grade medallion-architecture data lakehouse demonstrating modern data engineering practices: incremental loading, SCD Type 2 dimension tracking, dbt transformations, and layered data quality testing.

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────────────────┐
│ External APIs│───▶│  Airflow DAGs │───▶│         Lakehouse Storage         │
│ Alpha Vantage│     │  (Python      │     │                                   │
│ FRED         │     │   ingestion)  │     │  bronze/  →  silver/  →  gold/   │
└─────────────┘     └──────────────┘     │  (raw)       (cleaned, (marts,   │
                                           │              SCD2)     BI-ready) │
                                           └─────────────────────────────────┘
                                                    │              │
                                                    ▼              ▼
                                                DuckDB query   dbt models
                                                    │
                                                    ▼
                                          Data quality gates
                                          (dbt tests + Great Expectations)
```

### Medallion Layers

- **Bronze:** Raw API responses landed as-is (Parquet), append-only, immutable, partitioned by ingestion date. This is the audit trail, it never transforms before landing.

- **Silver:** Cleaned, deduplicated, typed, conformed data. Business keys established. SCD Type 2 applied to slowly-changing dimensions. Deduplication via window functions.

- **Gold:** Denormalized, aggregated marts built for specific consumption patterns:
  - `daily_price_summary` - OHLCV + rolling metrics (7d/30d MA, volatility)
  - `sector_performance` - Daily aggregated returns by sector (point-in-time-correct joins)
  - `macro_market_correlation` - Market returns with macro indicators (as-of joins)

## 🎯 Key Design Decisions

### Why land raw JSON in bronze?
Bronze is the source of truth. If a downstream bug is discovered, we can reprocess without re-calling rate-limited APIs. This design trades storage for resilience.

### Why partition by ingestion date, not trade date?
Preserves auditability. We know *when* we pulled the data even if the API backfills or corrects historical values later.

### Why dedupe in silver via window functions?
Alpha Vantage's compact mode returns the last 100 days on every call, creating intentional overlaps. We land everything in bronze and dedupe downstream by keeping the most recent ingestion per `(ticker, trade_date)`. This is simpler than stateful "only fetch new records" logic and more resilient to API pagination quirks.

### Why use dbt snapshots for SCD Type 2?
dbt's built-in snapshot feature implements SCD Type 2 correctly (validity windows, immutable history) without hand-rolled MERGE logic. It's testable, auditable, and standard.

### Why point-in-time joins in sector_performance?
Historical sector classifications must match the date of the price data — not today's classification. The PIT join ensures we use the sector that was actually true on each historical date by matching against SCD2 validity windows.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional, for MinIO/Postgres)
- API keys configured through `.env` (use `.env.example` as the template)

### Setup

```bash
# Clone and enter project
git clone <repo-url>
cd marketfeed_lakehouse

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run bronze ingestion
python ingestion/alpha_vantage.py
python ingestion/fred.py

# Build silver/gold layers with dbt
cd dbt
dbt deps
dbt seed
dbt snapshot
dbt run
dbt test

# Run data quality checks
python great_expectations/checks/freshness_check.py
```

### Generate Documentation

```bash
cd dbt
dbt docs generate
dbt docs serve --port 8081
```

Visit http://localhost:8081 to explore the interactive lineage graph and model documentation.

## 📊 Data Model

### Bronze Tables (Raw)
- `daily_prices_raw` — One row per API response with JSON blob + ingestion metadata
- `fred_series_raw` — One row per FRED series pull

### Silver Tables (Cleaned)
- `stg_stock_prices` — Grain: one row per (ticker, trade_date)
- `stg_macro_indicators` — Grain: one row per (series_id, observation_date)
- `dim_company` — SCD Type 2, grain: one row per (ticker, valid_from, valid_to)

### Gold Tables (Marts)
- `daily_price_summary` — Daily OHLCV + rolling metrics per ticker
- `sector_performance` — Daily aggregated returns by sector
- `macro_market_correlation` — Market-wide returns with macro context

## 🧪 Testing

### Unit Tests (Ingestion)

```bash
PYTHONPATH=. pytest tests/ -v
```

### dbt Tests

```bash
cd dbt
dbt test
```

### Data Quality Gates

```bash
python great_expectations/checks/freshness_check.py
```

## 🔄 CI/CD

GitHub Actions pipeline automatically:
1. Runs unit tests on ingestion scripts
2. Generates sample bronze fixtures
3. Builds dbt models (silver → gold)
4. Runs all dbt tests
5. Lints SQL with sqlfluff

See `.github/workflows/ci.yml` for details.

## 📈 What I'd Do Differently at Scale

1. **Storage:** Move from file-based DuckDB to Snowflake/BigQuery with proper table formats (Iceberg/Delta)
2. **Deduplication:** Replace window function dedup with MERGE-based upsert to avoid full-table scans
3. **Orchestration:** Add more sophisticated retry logic, data quality gates that block downstream runs, and SLA monitoring
4. **Incremental dbt:** Convert silver models to incremental materialization with proper merge keys
5. **Partitioning:** Partition silver/gold tables by date for query performance
6. **Observability:** Add dbt exposures, pipeline run logs, and Slack alerting on failures

## 🛠️ Tech Stack

- **Ingestion:** Python (requests, pandas, pyarrow)
- **Storage:** Local files (Parquet) + DuckDB
- **Transformation:** dbt-core with dbt-duckdb adapter
- **Orchestration:** Apache Airflow (ready to deploy)
- **Data Quality:** dbt tests + Great Expectations
- **CI/CD:** GitHub Actions
- **IaC:** Terraform (ready for cloud deployment)

## 📝 Project Structure

```
marketfeed_lakehouse/
├── .env.example             # Environment-variable template; copy to .env locally
├── .github/workflows/ci.yml # GitHub Actions: tests, dbt build, and SQL linting
├── .gitignore                # Local secrets, data, caches, and build artifacts
├── BUILD_STATUS.md           # Implementation and build status
├── LICENSE                   # MIT license
├── QUICKSTART.md             # Detailed end-to-end runbook
├── README.md                 # Project overview and usage
├── docker-compose.yml        # Optional MinIO and PostgreSQL services
├── requirements.txt          # Python, Airflow, dbt, testing, and quality dependencies
├── marketfeed-lakehouse-implementation-guide.md
│                             # Detailed implementation guide
├── dags/                     # Airflow orchestration
│   ├── marketfeed_bronze_dag.py
│   └── marketfeed_dbt_dag.py
├── dbt/                      # dbt transformation project
│   ├── dbt_project.yml       # Project configuration
│   ├── profiles.yml          # Local DuckDB profile
│   ├── packages.yml          # dbt package declarations
│   ├── package-lock.yml      # Resolved dbt package versions
│   ├── .sqlfluff             # SQL lint configuration
│   ├── macros/               # Reusable dbt macros
│   ├── models/
│   │   ├── sources.yml       # Bronze Parquet source definitions
│   │   ├── silver/            # Staging and dimension models plus tests
│   │   └── gold/              # Analytical marts plus tests
│   ├── seeds/                # Company metadata CSV
│   └── snapshots/            # SCD Type 2 company snapshot
├── docs/data_model.md        # Data model reference
├── great_expectations/      # Data quality checks
│   └── checks/freshness_check.py
├── infra/                    # Terraform infrastructure definitions
│   ├── main.tf
│   └── variables.tf
├── ingestion/                # API clients and bronze landing logic
│   ├── __init__.py
│   ├── alpha_vantage.py
│   └── fred.py
├── scripts/                  # Development and CI utilities
│   └── seed_ci_fixtures.py   # Generates synthetic bronze Parquet fixtures
└── tests/                    # Ingestion unit tests
  ├── conftest.py
  ├── test_alpha_vantage.py
  └── test_fred.py
```

Runtime data and generated files are intentionally not part of the source tree:
`data/` contains local Parquet and DuckDB output, while `dbt/target/`,
`dbt/dbt_packages/`, `dbt/logs/`, virtual environments, and Python caches are
created locally or by the build process and are excluded by `.gitignore`.

## 📚 Learning Resources

This project demonstrates:
- ✅ Medallion architecture (bronze/silver/gold)
- ✅ Incremental loading patterns
- ✅ SCD Type 2 with dbt snapshots
- ✅ Point-in-time-correct joins
- ✅ As-of joins for time-series correlation
- ✅ Idempotent ingestion design
- ✅ Layered data quality (dbt + GE)
- ✅ CI/CD for data pipelines
- ✅ Infrastructure as Code

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

This is a portfolio project, but feedback and suggestions are welcome via issues or PRs.

---

**Built to demonstrate production data engineering practices.**
