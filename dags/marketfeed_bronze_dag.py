"""
Airflow DAG for bronze layer ingestion.

Orchestrates daily ingestion of market data from Alpha Vantage and FRED APIs.
Demonstrates:
- Incremental loading with catchup
- Retry logic with exponential backoff
- Quality gates blocking downstream processing
- XCom for inter-task communication
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ingestion.alpha_vantage import fetch_daily_prices, land_to_bronze as land_prices
from ingestion.fred import fetch_series, land_to_bronze as land_fred, SERIES_IDS

# Tickers to track (limited for free API tier)
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"]

default_args = {
    "owner": "data-eng",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
}


def ingest_prices(**context):
    """
    Ingest daily stock prices from Alpha Vantage.

    Handles partial failures: if one ticker fails, continue with others
    and track failures in XCom for downstream alerting.
    """
    bronze_path = os.getenv("BRONZE_PATH", "/opt/airflow/data/bronze")
    failures = []

    for ticker in TICKERS:
        try:
            data = fetch_daily_prices(ticker)
            land_prices(ticker, data, bronze_path=bronze_path)
            context["ti"].log.info(f"✓ Ingested {ticker}")
        except Exception as e:
            error_msg = str(e)
            context["ti"].log.error(f"✗ Failed to ingest {ticker}: {error_msg}")
            failures.append({ticker: error_msg})
            # Continue with other tickers

    if failures:
        context["ti"].xcom_push(key="price_failures", value=failures)
        # Don't fail the task if only some tickers failed
        if len(failures) == len(TICKERS):
            raise Exception(f"All {len(TICKERS)} tickers failed to ingest")


def ingest_macro(**context):
    """Ingest macroeconomic indicators from FRED."""
    bronze_path = os.getenv("BRONZE_PATH", "/opt/airflow/data/bronze")

    for series_id in SERIES_IDS:
        data = fetch_series(series_id)
        land_fred(series_id, data, bronze_path=bronze_path)
        context["ti"].log.info(f"✓ Ingested {series_id}")


def quality_gate(**context):
    """
    Run data quality checks before allowing dbt to proceed.

    This prevents bad data from propagating to silver/gold layers.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from great_expectations.checks.freshness_check import check_bronze_freshness

    try:
        bronze_path = os.getenv("BRONZE_PATH", "/opt/airflow/data/bronze")
        check_bronze_freshness(bronze_path=bronze_path)
        context["ti"].log.info("✓ Quality gate passed")
    except ValueError as e:
        context["ti"].log.error(f"✗ Quality gate failed: {e}")
        raise


with DAG(
    dag_id="marketfeed_bronze_ingestion",
    default_args=default_args,
    description="Ingest market data to bronze layer",
    schedule_interval="0 22 * * 1-5",  # 10pm UTC, weekdays (after US market close)
    start_date=datetime(2026, 8, 1),
    catchup=True,  # Enable backfill for historical data
    max_active_runs=1,  # Prevent overlapping runs
    tags=["bronze", "market-data", "ingestion"],
) as dag:

    ingest_prices_task = PythonOperator(
        task_id="ingest_daily_prices",
        python_callable=ingest_prices,
        provide_context=True,
    )

    ingest_macro_task = PythonOperator(
        task_id="ingest_macro_indicators",
        python_callable=ingest_macro,
        provide_context=True,
    )

    quality_gate_task = PythonOperator(
        task_id="quality_gate_bronze",
        python_callable=quality_gate,
        provide_context=True,
    )

    # DAG flow: ingest both sources in parallel, then quality gate
    [ingest_prices_task, ingest_macro_task] >> quality_gate_task
