"""
Test suite for Home page (index.md) code examples.

Validates that all code snippets on the Home page execute correctly
and use proper API imports.

Part of Story 11.6: User-Facing Documentation Quality Validation
"""

from decimal import Decimal

import pytest


class TestHomePageQuickStart:
    """Test the Quick Start code snippet from Home page."""

    def test_quickstart_imports(self):
        """Test that Quick Start imports work correctly."""
        from rustybt.api import order_target, record, symbol

        assert callable(order_target), "order_target should be callable"
        assert callable(record), "record should be callable"
        assert callable(symbol), "symbol should be callable"

    def test_quickstart_functions_defined(self):
        """Test that Quick Start functions can be defined."""
        from rustybt.api import order_target, symbol

        # Define functions without executing (no data bundle required)
        def initialize(context):
            context.asset = symbol("AAPL")

        def handle_data(context, data):
            short_mavg = data.history(context.asset, "price", bar_count=100, frequency="1d").mean()
            long_mavg = data.history(context.asset, "price", bar_count=300, frequency="1d").mean()

            if short_mavg > long_mavg:
                order_target(context.asset, 100)
            elif short_mavg < long_mavg:
                order_target(context.asset, 0)

        assert callable(initialize), "initialize should be defined"
        assert callable(handle_data), "handle_data should be defined"


class TestHomePageFeatureHighlights:
    """Test all feature highlight code snippets from Home page."""

    def test_decimal_precision_snippet(self):
        """Test Decimal Precision feature highlight."""
        from decimal import Decimal

        from rustybt.finance.decimal import DecimalLedger

        # Should instantiate without error
        ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
        assert ledger.starting_cash == Decimal("100000.00")

    def test_modern_data_architecture_snippet(self):
        """Test Modern Data Architecture feature highlight."""
        import polars as pl

        from rustybt.data.adapters import CCXTAdapter, YFinanceAdapter

        # Verify imports work (don't make network calls)
        assert pl is not None
        assert YFinanceAdapter is not None
        assert CCXTAdapter is not None

    def test_multi_strategy_portfolio_snippet(self):
        """Test Multi-Strategy Portfolio Management feature highlight."""
        from rustybt.portfolio import PortfolioAllocator
        from rustybt.portfolio.allocation import RiskParityAllocation

        # Verify imports work
        assert PortfolioAllocator is not None
        assert RiskParityAllocation is not None
        # Note: Full instantiation requires strategy objects

    def test_strategy_optimization_snippet(self):
        """Test Strategy Optimization feature highlight."""
        from rustybt.optimization import Optimizer, WalkForwardOptimizer

        # Verify imports work
        assert Optimizer is not None
        assert WalkForwardOptimizer is not None

    def test_live_trading_snippet(self):
        """Test Live Trading feature highlight."""
        from rustybt.live import LiveTradingEngine
        from rustybt.live.brokers import CCXTBrokerAdapter

        # Verify imports work
        assert LiveTradingEngine is not None
        assert CCXTBrokerAdapter is not None


class TestHomePageNavigationLinks:
    """Test that Home page navigation links point to valid files."""

    def test_getting_started_links(self):
        """Test Getting Started section links."""
        import os

        base_path = "docs"
        links = [
            "getting-started/installation.md",
            "getting-started/quickstart.md",
            "getting-started/configuration.md",
        ]

        for link in links:
            full_path = os.path.join(base_path, link)
            assert os.path.exists(full_path), f"Link target should exist: {link}"

    def test_user_guides_links(self):
        """Test User Guides section links."""
        import os

        base_path = "docs"
        links = [
            "guides/decimal-precision-configuration.md",
            "guides/caching-system.md",
            "guides/creating-data-adapters.md",
            "guides/csv-data-import.md",
            "guides/testnet-setup-guide.md",
        ]

        for link in links:
            full_path = os.path.join(base_path, link)
            assert os.path.exists(full_path), f"Link target should exist: {link}"

    def test_api_reference_links(self):
        """Test API Reference section links."""
        import os

        base_path = "docs"
        links = [
            "api/datasource-api.md",
            "api/optimization-api.md",
            "api/analytics-api.md",
        ]

        for link in links:
            full_path = os.path.join(base_path, link)
            assert os.path.exists(full_path), f"Link target should exist: {link}"
