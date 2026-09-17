"""
Alpha Vantage API ingestion module for bronze layer.
Fetches daily stock price data and lands it raw to the bronze layer.
"""
import os
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any 


def get_api_key() -> str:
    """Get Alpha Vantage API key from environment."""
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable not set")
    return api_key


BASE_URL = "https://www.alphavantage.co/query"


def fetch_daily_prices(ticker: str, outputsize: str = "compact") -> Dict[Any, Any]:
    """
    Fetch full daily price history for a ticker. Idempotent — pure API read.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        outputsize: "compact" (last 100 days) or "full" (full history)

    Returns:
        Raw API response as dict

    Raises:
        ValueError: If API returns error or unexpected response
        requests.RequestException: If HTTP request fails
    """
    api_key = get_api_key()
    params = {
        "function": "TIME_SERIES_DAILY",  # Using free tier endpoint
        "symbol": ticker,
        "outputsize": outputsize,
        "apikey": api_key,
    }

    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Check for API errors
    if "Time Series (Daily)" not in data:
        error_msg = data.get("Note") or data.get("Error Message") or data.get("Information") or "Unknown error"
        raise ValueError(f"Unexpected response for {ticker}: {error_msg}")

    return data


def land_to_bronze(ticker: str, raw_response: Dict[Any, Any], bronze_path: str = "./data/bronze") -> Path:
    """
    Land raw API response as-is, partitioned by ingestion date. Never transform here.

    This is the "source of truth" — if we discover a bug downstream later, we can
    reprocess from bronze without re-calling the rate-limited API.

    Args:
        ticker: Stock ticker symbol
        raw_response: Raw API response dict
        bronze_path: Base path for bronze layer storage

    Returns:
        Path to the written file
    """
    ingest_ts = datetime.now(timezone.utc)
    partition = ingest_ts.strftime("%Y-%m-%d")
    out_dir = Path(bronze_path) / "daily_prices_raw" / f"ingest_date={partition}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Create DataFrame with metadata
    df = pd.DataFrame([{
        "ticker": ticker,
        "raw_payload": raw_response,
        "ingested_at": ingest_ts.isoformat(),
        "source": "alpha_vantage",
        "api_function": "TIME_SERIES_DAILY",
    }])

    # Write as Parquet for efficient columnar storage
    output_file = out_dir / f"{ticker}_{ingest_ts.strftime('%H%M%S')}.parquet"
    df.to_parquet(output_file, index=False)

    return output_file


if __name__ == "__main__":
    # Example usage: ingest a few tickers (limited to avoid rate limits on free tier)
    from dotenv import load_dotenv
    import time
    load_dotenv()

    TICKERS = ["AAPL", "MSFT", "GOOGL"]  # Reduced for free tier rate limits

    for ticker in TICKERS:
        try:
            print(f"Fetching {ticker}...")
            data = fetch_daily_prices(ticker)
            output_path = land_to_bronze(ticker, data)
            print(f"✓ Landed {ticker} to {output_path}")
        except Exception as e:
            print(f"✗ Failed to ingest {ticker}: {e}")
