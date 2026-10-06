"""
Generate sample bronze data fixtures for CI testing.

This creates realistic but minimal Parquet files matching the bronze schema,
so CI can test dbt models without calling live APIs (which would be flaky
and rate-limited).

Fixtures are partitioned under *today's* date by default because the
Great Expectations freshness gate (great_expectations/checks/freshness_check.py)
compares the latest ingest partition against date.today(). A hardcoded date
would make the freshness gate fail in CI.
"""
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


def create_sample_price_data(
    ingest_date: date | None = None,
    output_root: Path | str = Path("data/bronze"),
):
    """Create sample stock price bronze data."""
    ingest_date = ingest_date or date.today()
    ingest_date_str = ingest_date.isoformat()

    base_date = datetime(2026, 8, 20).date()
    tickers = ["AAPL", "MSFT", "GOOGL"]

    output_dir = Path(output_root) / "daily_prices_raw" / f"ingest_date={ingest_date_str}"
    output_dir.mkdir(parents=True, exist_ok=True)

    ingested_at = datetime.combine(ingest_date, datetime.min.time()).isoformat()

    for ticker in tickers:
        # Create realistic time series data
        time_series = {}
        for i in range(10):  # 10 days of data
            trade_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            base_price = 150.0 + (i * 2)
            time_series[trade_date] = {
                "1. open": str(base_price),
                "2. high": str(base_price + 2),
                "3. low": str(base_price - 2),
                "4. close": str(base_price + 1),
                "5. volume": str(1000000 + i * 10000)
            }

        raw_payload = {
            "Meta Data": {
                "1. Information": "Daily Prices",
                "2. Symbol": ticker
            },
            "Time Series (Daily)": time_series
        }

        df = pd.DataFrame([{
            "ticker": ticker,
            "raw_payload": raw_payload,
            "ingested_at": ingested_at,
            "source": "alpha_vantage",
            "api_function": "TIME_SERIES_DAILY"
        }])

        output_file = output_dir / f"{ticker}_test.parquet"
        df.to_parquet(output_file, index=False)
        print(f"Created {output_file}")


def create_sample_fred_data(
    ingest_date: date | None = None,
    output_root: Path | str = Path("data/bronze"),
):
    """Create sample FRED macro data."""
    ingest_date = ingest_date or date.today()
    ingest_date_str = ingest_date.isoformat()

    series = {
        "CPIAUCSL": [("2026-01-01", 300.0), ("2026-02-01", 301.0), ("2026-03-01", 302.0)],
        "UNRATE": [("2026-01-01", 3.8), ("2026-02-01", 3.7), ("2026-03-01", 3.9)],
        "FEDFUNDS": [("2026-01-01", 5.25), ("2026-02-01", 5.25), ("2026-03-01", 5.50)],
        "GDP": [("2026-01-01", 27000.0), ("2026-04-01", 27500.0)]
    }

    output_dir = Path(output_root) / "fred_series_raw" / f"ingest_date={ingest_date_str}"
    output_dir.mkdir(parents=True, exist_ok=True)

    ingested_at = datetime.combine(ingest_date, datetime.min.time()).isoformat()

    for series_id, observations in series.items():
        raw_payload = {
            "observations": [
                {"date": obs_date, "value": str(value)}
                for obs_date, value in observations
            ]
        }

        df = pd.DataFrame([{
            "series_id": series_id,
            "raw_payload": raw_payload,
            "ingested_at": ingested_at,
            "source": "fred"
        }])

        output_file = output_dir / f"{series_id}_test.parquet"
        df.to_parquet(output_file, index=False)
        print(f"Created {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sample bronze data for CI")
    parser.add_argument(
        "--ingest-date",
        type=date.fromisoformat,
        default=None,
        help="Partition date for the fixtures (default: today)",
    )
    parser.add_argument(
        "--output-root",
        default="data/bronze",
        help="Bronze root directory (default: data/bronze)",
    )
    args = parser.parse_args()

    print("Generating sample bronze data for CI...")
    create_sample_price_data(ingest_date=args.ingest_date, output_root=args.output_root)
    create_sample_fred_data(ingest_date=args.ingest_date, output_root=args.output_root)
    print("✓ CI fixtures generated successfully")
