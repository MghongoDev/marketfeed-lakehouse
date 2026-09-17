"""Ingestion package initialization."""
from ingestion.alpha_vantage import fetch_daily_prices, land_to_bronze as land_prices
from ingestion.fred import fetch_series, land_to_bronze as land_fred, SERIES_IDS

__all__ = [
    "fetch_daily_prices",
    "land_prices",
    "fetch_series",
    "land_fred",
    "SERIES_IDS",
]
