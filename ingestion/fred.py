"""
FRED (Federal Reserve Economic Data) API ingestion module for bronze layer.
Fetches macroeconomic indicators and lands them raw.
"""
import os
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


def get_api_key() -> str:
    """Get FRED API key from environment."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY environment variable not set")
    return api_key


BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Macroeconomic indicators to track
SERIES_IDS = [
    "CPIAUCSL",   # Consumer Price Index (CPI)
    "UNRATE",     # Unemployment Rate
    "FEDFUNDS",   # Federal Funds Rate
    "GDP",        # Gross Domestic Product
]


def fetch_series(series_id: str) -> Dict[Any, Any]:
    """
    Fetch observations for a FRED series.

    Args:
        series_id: FRED series identifier (e.g., "CPIAUCSL")

    Returns:
        Raw API response as dict

    Raises:
        ValueError: If API returns error
        requests.RequestException: If HTTP request fails
    """
    api_key = get_api_key()
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }

    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Check for API errors
    if "observations" not in data:
        error_msg = data.get("error_message", "Unknown error")
        raise ValueError(f"Unexpected response for {series_id}: {error_msg}")

    return data


def land_to_bronze(series_id: str, raw_response: Dict[Any, Any], bronze_path: str = "./data/bronze") -> Path:
    """
    Land raw FRED API response as-is, partitioned by ingestion date.

    Args:
        series_id: FRED series identifier
        raw_response: Raw API response dict
        bronze_path: Base path for bronze layer storage

    Returns:
        Path to the written file
    """
    ingest_ts = datetime.now(timezone.utc)
    partition = ingest_ts.strftime("%Y-%m-%d")
    out_dir = Path(bronze_path) / "fred_series_raw" / f"ingest_date={partition}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Create DataFrame with metadata
    df = pd.DataFrame([{
        "series_id": series_id,
        "raw_payload": raw_response,
        "ingested_at": ingest_ts.isoformat(),
        "source": "fred",
    }])

    # Write as Parquet
    output_file = out_dir / f"{series_id}_{ingest_ts.strftime('%H%M%S')}.parquet"
    df.to_parquet(output_file, index=False)

    return output_file


if __name__ == "__main__":
    # Example usage: ingest macro indicators
    from dotenv import load_dotenv
    load_dotenv()

    for series_id in SERIES_IDS:
        try:
            print(f"Fetching {series_id}...")
            data = fetch_series(series_id)
            output_path = land_to_bronze(series_id, data)
            print(f"✓ Landed {series_id} to {output_path}")
        except Exception as e:
            print(f"✗ Failed to ingest {series_id}: {e}")
