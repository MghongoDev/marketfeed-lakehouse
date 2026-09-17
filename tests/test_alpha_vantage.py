"""
Unit tests for Alpha Vantage ingestion module.
"""
import pytest
import responses
from pathlib import Path
from ingestion.alpha_vantage import fetch_daily_prices, land_to_bronze


@responses.activate
def test_fetch_daily_prices_success():
    """Test successful API call with valid response."""
    responses.add(
        responses.GET,
        "https://www.alphavantage.co/query",
        json={
            "Meta Data": {"1. Information": "Daily Prices"},
            "Time Series (Daily)": {
                "2026-08-28": {
                    "1. open": "150.00",
                    "2. high": "152.00",
                    "3. low": "149.00",
                    "4. close": "151.50",
                    "5. volume": "1000000"
                }
            }
        },
        status=200,
    )

    result = fetch_daily_prices("AAPL")
    assert "Time Series (Daily)" in result
    assert "2026-08-28" in result["Time Series (Daily)"]


@responses.activate
def test_fetch_daily_prices_api_error():
    """Test API error handling."""
    responses.add(
        responses.GET,
        "https://www.alphavantage.co/query",
        json={"Error Message": "Invalid API call"},
        status=200,
    )

    with pytest.raises(ValueError) as exc_info:
        fetch_daily_prices("BADTICKER")
    assert "Invalid API call" in str(exc_info.value)


@responses.activate
def test_fetch_daily_prices_premium_endpoint_error():
    """Test handling of premium endpoint message."""
    responses.add(
        responses.GET,
        "https://www.alphavantage.co/query",
        json={"Information": "This is a premium endpoint"},
        status=200,
    )

    with pytest.raises(ValueError) as exc_info:
        fetch_daily_prices("AAPL")
    assert "premium endpoint" in str(exc_info.value)


def test_land_to_bronze_creates_file(tmp_path):
    """Test that landing to bronze creates a properly structured file."""
    mock_response = {
        "Meta Data": {"1. Information": "Daily Prices"},
        "Time Series (Daily)": {
            "2026-08-28": {"4. close": "150.00"}
        }
    }

    output_file = land_to_bronze("AAPL", mock_response, bronze_path=str(tmp_path))

    assert output_file.exists()
    assert "daily_prices_raw" in str(output_file)
    assert "ingest_date=" in str(output_file)
    assert output_file.suffix == ".parquet"


def test_land_to_bronze_partition_structure(tmp_path):
    """Test that files are partitioned by ingestion date."""
    mock_response = {
        "Time Series (Daily)": {"2026-08-28": {"4. close": "150.00"}}
    }

    output_file = land_to_bronze("AAPL", mock_response, bronze_path=str(tmp_path))

    # Verify directory structure
    assert "ingest_date=" in str(output_file.parent)
    assert output_file.parent.parent.name == "daily_prices_raw"
