"""Shared test fixtures for decimal finance tests."""

import pytest


# Mock Asset class for testing
class MockAsset:
    """Mock asset for testing."""

    def __init__(self, symbol: str, asset_class: str = "equity"):
        self.symbol = symbol
        self.asset_class = asset_class

    def __repr__(self):
        return f"{self.asset_class}({self.symbol})"

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        return self.symbol == other.symbol


@pytest.fixture
def equity_asset():
    """Create equity asset fixture."""
    return MockAsset("AAPL", "equity")


@pytest.fixture
def crypto_asset():
    """Create crypto asset fixture."""
    return MockAsset("BTC", "crypto")
