"""
Generate sample bronze data fixtures for CI testing.

This creates realistic but minimal Parquet files matching the bronze schema,
so CI can test dbt models without calling live APIs (which would be flaky
and rate-limited).
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta


def create_sample_price_data():
    """Create sample stock price bronze data."""
    base_date = datetime(2026, 8, 20)
    tickers = ["AAPL", "MSFT", "GOOGL"]

    output_dir = Path("data/bronze/daily_prices_raw/ingest_date=2026-08-31")
    output_dir.mkdir(parents=True, exist_ok=True)

    for ticker in tickers:
        # Create realistic time series data
        time_series = {}
        for i in range(10):  # 10 days of data
            date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            base_price = 150.0 + (i * 2)
            time_series[date] = {
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
            "ingested_at": datetime(2026, 8, 31, 12, 0, 0).isoformat(),
            "source": "alpha_vantage",
            "api_function": "TIME_SERIES_DAILY"
        }])

        output_file = output_dir / f"{ticker}_test.parquet"
        df.to_parquet(output_file, index=False)
        print(f"Created {output_file}")


def create_sample_fred_data():
    """Create sample FRED macro data."""
    series = {
        "CPIAUCSL": [("2026-01-01", 300.0), ("2026-02-01", 301.0), ("2026-03-01", 302.0)],
        "UNRATE": [("2026-01-01", 3.8), ("2026-02-01", 3.7), ("2026-03-01", 3.9)],
        "FEDFUNDS": [("2026-01-01", 5.25), ("2026-02-01", 5.25), ("2026-03-01", 5.50)],
        "GDP": [("2026-01-01", 27000.0), ("2026-04-01", 27500.0)]
    }

    output_dir = Path("data/bronze/fred_series_raw/ingest_date=2026-08-31")
    output_dir.mkdir(parents=True, exist_ok=True)

    for series_id, observations in series.items():
        raw_payload = {
            "observations": [
                {"date": date, "value": str(value)}
                for date, value in observations
            ]
        }

        df = pd.DataFrame([{
            "series_id": series_id,
            "raw_payload": raw_payload,
            "ingested_at": datetime(2026, 8, 31, 12, 0, 0).isoformat(),
            "source": "fred"
        }])

        output_file = output_dir / f"{series_id}_test.parquet"
        df.to_parquet(output_file, index=False)
        print(f"Created {output_file}")


if __name__ == "__main__":
    print("Generating sample bronze data for CI...")
    create_sample_price_data()
    create_sample_fred_data()
    print("✓ CI fixtures generated successfully")
