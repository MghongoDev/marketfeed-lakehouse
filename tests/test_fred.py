"""
Unit tests for FRED ingestion module.
"""
import pytest
import responses
from pathlib import Path
from ingestion.fred import fetch_series, land_to_bronze


@responses.activate
def test_fetch_series_success():
    """Test successful FRED API call."""
    responses.add(
        responses.GET,
        "https://api.stlouisfed.org/fred/series/observations",
        json={
            "observations": [
                {"date": "2026-01-01", "value": "100.0"},
                {"date": "2026-02-01", "value": "101.0"},
            ]
        },
        status=200,
    )

    result = fetch_series("CPIAUCSL")
    assert "observations" in result
    assert len(result["observations"]) == 2


@responses.activate
def test_fetch_series_api_error():
    """Test FRED API error handling."""
    responses.add(
        responses.GET,
        "https://api.stlouisfed.org/fred/series/observations",
        json={"error_message": "Bad Request"},
        status=200,
    )

    with pytest.raises(ValueError) as exc_info:
        fetch_series("INVALID")
    assert "Bad Request" in str(exc_info.value)


def test_land_to_bronze_creates_file(tmp_path):
    """Test that landing to bronze creates a properly structured file."""
    mock_response = {
        "observations": [
            {"date": "2026-01-01", "value": "100.0"}
        ]
    }

    output_file = land_to_bronze("CPIAUCSL", mock_response, bronze_path=str(tmp_path))

    assert output_file.exists()
    assert "fred_series_raw" in str(output_file)
    assert "ingest_date=" in str(output_file)
    assert output_file.suffix == ".parquet"


def test_land_to_bronze_partition_structure(tmp_path):
    """Test that files are partitioned by ingestion date."""
    mock_response = {
        "observations": [{"date": "2026-01-01", "value": "100.0"}]
    }

    output_file = land_to_bronze("CPIAUCSL", mock_response, bronze_path=str(tmp_path))

    # Verify directory structure
    assert "ingest_date=" in str(output_file.parent)
    assert output_file.parent.parent.name == "fred_series_raw"
