"""
Data quality checks using Great Expectations.

Implements freshness and volume checks that dbt's column-level tests don't
cover well. These act as quality gates in the pipeline.
"""
import duckdb
from datetime import date, timedelta
from pathlib import Path


def check_bronze_freshness(bronze_path: str = "data/bronze", max_days_stale: int = 3):
    """
    Check that bronze data is not too stale.

    Args:
        bronze_path: Path to bronze layer
        max_days_stale: Maximum acceptable staleness in days (allows for weekends)

    Raises:
        ValueError: If data is too stale
    """
    parquet_files = list(Path(bronze_path).glob("daily_prices_raw/**/*.parquet"))
    if not parquet_files:
        raise ValueError(f"No bronze data found in {bronze_path}")

    con = duckdb.connect()
    result = con.execute(f"""
        SELECT max(cast(ingested_at as date)) as latest_ingest
        FROM read_parquet('{bronze_path}/daily_prices_raw/**/*.parquet', hive_partitioning=1)
    """).fetchone()

    if result[0] is None:
        raise ValueError("Could not determine latest ingestion date")

    latest = result[0]
    days_stale = (date.today() - latest).days

    if days_stale > max_days_stale:
        raise ValueError(
            f"Bronze data is {days_stale} days stale (latest: {latest}). "
            f"Maximum allowed: {max_days_stale} days"
        )

    print(f"✓ Freshness OK — latest ingest: {latest} ({days_stale} days old)")
    return True


def check_row_count_within_range(
    db_path: str = "data/marketfeed.duckdb",
    expected_min: int = 2,
    expected_max: int = 20
):
    """
    Check that we have a reasonable number of tickers in the latest data.

    Args:
        db_path: Path to DuckDB database
        expected_min: Minimum expected ticker count
        expected_max: Maximum expected ticker count

    Raises:
        ValueError: If ticker count is outside expected range
    """
    if not Path(db_path).exists():
        raise ValueError(f"Database not found: {db_path}")

    con = duckdb.connect(db_path, read_only=True)
    result = con.execute("""
        SELECT count(distinct ticker) as ticker_count
        FROM main_silver.stg_stock_prices
        WHERE trade_date = (SELECT max(trade_date) FROM main_silver.stg_stock_prices)
    """).fetchone()

    count = result[0]

    if not (expected_min <= count <= expected_max):
        raise ValueError(
            f"Unexpected ticker count for latest date: {count} "
            f"(expected between {expected_min} and {expected_max})"
        )

    print(f"✓ Volume check OK — {count} tickers in latest data")
    return True


def check_no_negative_prices(db_path: str = "data/marketfeed.duckdb"):
    """
    Sanity check: ensure no negative prices in silver layer.

    Args:
        db_path: Path to DuckDB database

    Raises:
        ValueError: If negative prices are found
    """
    if not Path(db_path).exists():
        raise ValueError(f"Database not found: {db_path}")

    con = duckdb.connect(db_path, read_only=True)
    result = con.execute("""
        SELECT count(*) as negative_count
        FROM main_silver.stg_stock_prices
        WHERE close_price < 0 OR open_price < 0 OR high_price < 0 OR low_price < 0
    """).fetchone()

    negative_count = result[0]

    if negative_count > 0:
        raise ValueError(f"Found {negative_count} rows with negative prices!")

    print(f"✓ Price sanity check OK — no negative prices")
    return True


if __name__ == "__main__":
    print("Running data quality checks...")
    try:
        check_bronze_freshness()
        check_row_count_within_range()
        check_no_negative_prices()
        print("\n✓ All quality checks passed!")
    except ValueError as e:
        print(f"\n✗ Quality check failed: {e}")
        exit(1)
