"""
CI freshness gate.

Runs check_bronze_freshness (Great Expectations checks) against the bronze
layer and exits non-zero when data is stale or missing, so GitHub Actions can
fail the job on the check's result.

freshness_check.py is loaded by file path rather than package import because
the project's great_expectations/ directory is shadowed by the installed
great_expectations pip package whenever the project root is on sys.path.

Usage:
    python scripts/run_freshness_gate.py [--bronze-path PATH] [--max-days-stale N]
"""
import argparse
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRESHNESS_CHECK_PATH = PROJECT_ROOT / "great_expectations" / "checks" / "freshness_check.py"


def load_freshness_check():
    """Load great_expectations/checks/freshness_check.py as a standalone module."""
    spec = importlib.util.spec_from_file_location("freshness_check", FRESHNESS_CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bronze-layer freshness gate")
    parser.add_argument(
        "--bronze-path",
        default=str(PROJECT_ROOT / "data" / "bronze"),
        help="Path to the bronze layer (default: <project root>/data/bronze)",
    )
    parser.add_argument(
        "--max-days-stale",
        type=int,
        default=3,
        help="Maximum acceptable staleness in days (default: 3, allows weekends)",
    )
    args = parser.parse_args()

    freshness_check = load_freshness_check()
    try:
        freshness_check.check_bronze_freshness(
            bronze_path=args.bronze_path,
            max_days_stale=args.max_days_stale,
        )
    except ValueError as e:
        print(f"✗ Freshness gate failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
