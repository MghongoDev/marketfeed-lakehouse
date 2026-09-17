"""Test configuration and fixtures."""
import os
import pytest


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set test environment variables for all tests."""
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test_key_123")
    monkeypatch.setenv("FRED_API_KEY", "test_fred_key_456")
