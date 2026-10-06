"""
Tests for CI fixture generation and the Great Expectations freshness gate.

The fixtures must be date-dynamic (partitioned under today's date by default)
because check_bronze_freshness compares the latest ingest partition against
date.today(). Hardcoded fixture dates make the freshness gate fail in CI.

freshness_check.py is loaded by file path because the project's
great_expectations/ directory is shadowed by the installed great_expectations
pip package when the project root is on sys.path.
"""
import importlib.util
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from scripts.seed_ci_fixtures import (
    create_sample_fred_data,
    create_sample_price_data,
)


@pytest.fixture(scope="session")
def freshness_check():
    """Load great_expectations/checks/freshness_check.py without package import."""
    path = PROJECT_ROOT / "great_expectations" / "checks" / "freshness_check.py"
    spec = importlib.util.spec_from_file_location("freshness_check_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixture_root(tmp_path):
    """Isolated bronze root so tests never touch the repo's data/ directory."""
    root = tmp_path / "bronze"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# Fixture generation (scripts/seed_ci_fixtures.py)
# ---------------------------------------------------------------------------


def test_price_fixture_defaults_to_today_partition(fixture_root):
    create_sample_price_data(output_root=fixture_root)

    partition_dir = fixture_root / "daily_prices_raw" / f"ingest_date={date.today().isoformat()}"
    parquet_files = sorted(partition_dir.glob("*.parquet"))
    assert [f.name for f in parquet_files] == [
        "AAPL_test.parquet",
        "GOOGL_test.parquet",
        "MSFT_test.parquet",
    ]


def test_fixture_ingested_at_matches_partition_date(fixture_root):
    create_sample_price_data(ingest_date=date(2026, 1, 15), output_root=fixture_root)
    create_sample_fred_data(ingest_date=date(2026, 1, 15), output_root=fixture_root)

    import duckdb

    for rel_path in (
        "daily_prices_raw/ingest_date=2026-01-15/*.parquet",
        "fred_series_raw/ingest_date=2026-01-15/*.parquet",
    ):
        con = duckdb.connect()
        try:
            rows = con.execute(
                f"""
                SELECT DISTINCT cast(ingested_at as date) AS d
                FROM read_parquet('{fixture_root / rel_path}')
                """
            ).fetchall()
        finally:
            con.close()
        assert rows == [(date(2026, 1, 15),)]


def test_fixture_payload_schema_matches_bronze_contract(fixture_root):
    """Bronze columns must match what dbt's sources.yml and silver models expect."""
    create_sample_price_data(output_root=fixture_root)
    create_sample_fred_data(output_root=fixture_root)

    import pandas as pd

    prices = pd.read_parquet(
        next((fixture_root / "daily_prices_raw").glob("ingest_date=*/*.parquet"))
    )
    assert set(prices.columns) == {
        "ticker",
        "raw_payload",
        "ingested_at",
        "source",
        "api_function",
    }
    assert "Time Series (Daily)" in prices.iloc[0]["raw_payload"]

    fred = pd.read_parquet(
        next((fixture_root / "fred_series_raw").glob("ingest_date=*/*.parquet"))
    )
    assert set(fred.columns) == {"series_id", "raw_payload", "ingested_at", "source"}
    assert "observations" in fred.iloc[0]["raw_payload"]


# ---------------------------------------------------------------------------
# Freshness gate (great_expectations/checks/freshness_check.py)
# ---------------------------------------------------------------------------


def test_freshness_passes_on_fresh_fixtures(freshness_check, fixture_root):
    create_sample_price_data(output_root=fixture_root)
    create_sample_fred_data(output_root=fixture_root)

    assert freshness_check.check_bronze_freshness(bronze_path=str(fixture_root)) is True


def test_freshness_fails_on_stale_fixtures(freshness_check, fixture_root):
    stale_date = date.today() - timedelta(days=10)
    create_sample_price_data(ingest_date=stale_date, output_root=fixture_root)

    with pytest.raises(ValueError, match="days stale"):
        freshness_check.check_bronze_freshness(
            bronze_path=str(fixture_root), max_days_stale=3
        )


def test_freshness_fails_when_no_bronze_data(freshness_check, tmp_path):
    with pytest.raises(ValueError, match="No bronze data"):
        freshness_check.check_bronze_freshness(bronze_path=str(tmp_path))


# ---------------------------------------------------------------------------
# CI runner contract (scripts/run_freshness_gate.py)
# ---------------------------------------------------------------------------


def _run_gate(fixture_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_freshness_gate.py"),
            "--bronze-path",
            str(fixture_root),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_gate_exits_zero_on_fresh_fixtures(fixture_root):
    create_sample_price_data(output_root=fixture_root)

    result = _run_gate(fixture_root)
    assert result.returncode == 0, result.stderr
    assert "Freshness OK" in result.stdout


def test_gate_exits_one_on_stale_fixtures(fixture_root):
    stale_date = date.today() - timedelta(days=10)
    create_sample_price_data(ingest_date=stale_date, output_root=fixture_root)

    result = _run_gate(fixture_root)
    assert result.returncode == 1
    assert "days stale" in result.stdout
