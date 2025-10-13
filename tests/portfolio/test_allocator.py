"""Comprehensive tests for PortfolioAllocator.

Tests cover:
- Unit tests for basic operations
- Property-based tests for invariants
- Integration tests for multi-strategy scenarios
"""

from decimal import Decimal

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.portfolio.allocator import (
    PortfolioAllocator,
    StrategyPerformance,
    StrategyState,
)


# Mock strategy classes for testing
class MockStrategy:
    """Mock strategy for testing."""

    def __init__(self):
        self.handle_data_called = False
        self.last_ledger = None
        self.last_data = None

    def handle_data(self, ledger, data):
        """Mock handle_data implementation."""
        self.handle_data_called = True
        self.last_ledger = ledger
        self.last_data = data


class TimestampTrackingStrategy:
    """Strategy that tracks timestamps for synchronization testing."""

    def __init__(self):
        self.last_timestamp = None

    def handle_data(self, ledger, data):
        """Track timestamp from execution."""
        # In real scenario, would get timestamp from data
        # For testing, we'll set it externally
        pass


class MockPosition:
    """Mock position for testing."""

    pass


# Unit Tests
class TestPortfolioAllocatorBasics:
    """Test basic portfolio allocator operations."""

    def test_add_strategy_with_capital_allocation(self):
        """Add strategy with capital allocation."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Create mock strategy
        strategy = MockStrategy()

        # Add strategy with 30% allocation
        allocation = portfolio.add_strategy(
            strategy_id="test_strategy", strategy=strategy, allocation_pct=Decimal("0.30")
        )

        # Verify allocation
        assert allocation.strategy_id == "test_strategy"
        assert allocation.allocated_capital == Decimal("30000.00")
        assert allocation.state == StrategyState.RUNNING
        assert allocation.ledger.cash == Decimal("30000.00")

        # Verify portfolio state
        assert portfolio.allocated_capital == Decimal("30000.00")
        assert len(portfolio.strategies) == 1

    def test_add_strategy_exceeding_100_percent(self):
        """Adding strategy that exceeds 100% allocation raises error."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add first strategy (70%)
        portfolio.add_strategy(
            strategy_id="strategy1", strategy=MockStrategy(), allocation_pct=Decimal("0.70")
        )

        # Try to add second strategy (50%) - should fail
        with pytest.raises(ValueError, match="exceed 100%"):
            portfolio.add_strategy(
                strategy_id="strategy2", strategy=MockStrategy(), allocation_pct=Decimal("0.50")
            )

    def test_add_duplicate_strategy_id(self):
        """Adding strategy with duplicate ID raises error."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add first strategy
        portfolio.add_strategy(
            strategy_id="test", strategy=MockStrategy(), allocation_pct=Decimal("0.30")
        )

        # Try to add with same ID
        with pytest.raises(ValueError, match="already exists"):
            portfolio.add_strategy(
                strategy_id="test", strategy=MockStrategy(), allocation_pct=Decimal("0.20")
            )

    def test_execute_bar_across_all_strategies(self):
        """Execute bar processes all active strategies."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add multiple strategies
        strategy1 = MockStrategy()
        strategy2 = MockStrategy()

        portfolio.add_strategy("strategy1", strategy1, Decimal("0.50"))
        portfolio.add_strategy("strategy2", strategy2, Decimal("0.30"))

        # Execute bar
        timestamp = pd.Timestamp("2023-01-01")
        data = {"AAPL": {"price": Decimal("150.00")}}

        portfolio.execute_bar(timestamp, data)

        # Verify both strategies executed
        assert strategy1.handle_data_called
        assert strategy2.handle_data_called

        # Verify performance updated
        alloc1 = portfolio.strategies["strategy1"]
        alloc2 = portfolio.strategies["strategy2"]

        assert len(alloc1.performance.timestamps) == 1
        assert len(alloc2.performance.timestamps) == 1

    def test_rebalance_capital_between_strategies(self):
        """Rebalance transfers capital between strategies."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add two strategies
        portfolio.add_strategy("strategy1", MockStrategy(), Decimal("0.50"))
        portfolio.add_strategy("strategy2", MockStrategy(), Decimal("0.30"))

        # Initial state
        alloc1 = portfolio.strategies["strategy1"]
        alloc2 = portfolio.strategies["strategy2"]

        assert alloc1.allocated_capital == Decimal("50000.00")
        assert alloc2.allocated_capital == Decimal("30000.00")

        # Rebalance: strategy1 40%, strategy2 40%
        portfolio.rebalance({"strategy1": Decimal("0.40"), "strategy2": Decimal("0.40")})

        # Verify new allocations
        assert alloc1.allocated_capital == Decimal("40000.00")
        assert alloc2.allocated_capital == Decimal("40000.00")

        # Verify cash transferred
        assert alloc1.ledger.cash == Decimal("40000.00")  # Reduced from 50k
        assert alloc2.ledger.cash == Decimal("40000.00")  # Increased from 30k

    def test_rebalance_exceeding_100_percent(self):
        """Rebalancing with >100% total raises error."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        portfolio.add_strategy("strategy1", MockStrategy(), Decimal("0.50"))
        portfolio.add_strategy("strategy2", MockStrategy(), Decimal("0.30"))

        # Try to rebalance to >100%
        with pytest.raises(ValueError, match="exceed 100%"):
            portfolio.rebalance({"strategy1": Decimal("0.60"), "strategy2": Decimal("0.50")})

    def test_aggregate_portfolio_metrics(self):
        """Aggregate metrics calculation across strategies."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add strategies
        portfolio.add_strategy("strategy1", MockStrategy(), Decimal("0.50"))
        portfolio.add_strategy("strategy2", MockStrategy(), Decimal("0.30"))

        # Simulate some returns
        alloc1 = portfolio.strategies["strategy1"]
        alloc2 = portfolio.strategies["strategy2"]

        # Update values (10% gain for strategy1, -5% for strategy2)
        alloc1.ledger.cash = Decimal("55000.00")
        alloc2.ledger.cash = Decimal("28500.00")

        # Get metrics
        metrics = portfolio.get_portfolio_metrics()

        # Total value = 55k + 28.5k = 83.5k
        assert Decimal(metrics["total_value"]) == Decimal("83500.00")

        # Allocated capital was 80k total
        assert Decimal(metrics["allocated_capital"]) == Decimal("80000.00")

    def test_remove_strategy_and_return_capital(self):
        """Remove strategy returns capital to portfolio."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add strategy
        portfolio.add_strategy("test_strategy", MockStrategy(), Decimal("0.30"))

        assert portfolio.allocated_capital == Decimal("30000.00")

        # Remove strategy
        returned_capital = portfolio.remove_strategy("test_strategy", liquidate=True)

        # Verify removal
        assert "test_strategy" not in portfolio.strategies
        assert portfolio.allocated_capital == Decimal("0")

        # Capital returned should equal allocated (no P&L in this test)
        assert returned_capital == Decimal("30000.00")

    def test_remove_nonexistent_strategy(self):
        """Removing non-existent strategy raises error."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        with pytest.raises(KeyError, match="not found"):
            portfolio.remove_strategy("nonexistent")

    def test_pause_and_resume_strategy(self):
        """Pause and resume strategy execution."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        strategy = MockStrategy()
        portfolio.add_strategy("test", strategy, Decimal("0.30"))

        # Pause strategy
        portfolio.pause_strategy("test")
        assert portfolio.strategies["test"].state == StrategyState.PAUSED
        assert not portfolio.strategies["test"].is_active

        # Resume strategy
        portfolio.resume_strategy("test")
        assert portfolio.strategies["test"].state == StrategyState.RUNNING
        assert portfolio.strategies["test"].is_active

    def test_strategy_isolation_verification(self):
        """Verify strategies cannot interfere with each other."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add two strategies
        portfolio.add_strategy("strategy1", MockStrategy(), Decimal("0.50"))
        portfolio.add_strategy("strategy2", MockStrategy(), Decimal("0.30"))

        alloc1 = portfolio.strategies["strategy1"]
        alloc2 = portfolio.strategies["strategy2"]

        # Verify separate ledgers
        assert alloc1.ledger is not alloc2.ledger

        # Modify strategy1's ledger
        alloc1.ledger.cash = Decimal("25000.00")

        # Verify strategy2's ledger unchanged
        assert alloc2.ledger.cash == Decimal("30000.00")

        # Add position to strategy1
        alloc1.ledger.positions = {"AAPL": MockPosition()}

        # Verify strategy2 has no positions
        assert len(alloc2.ledger.positions) == 0

    def test_cash_conservation_validation(self):
        """Validate total cash is conserved across strategies."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add strategies
        portfolio.add_strategy("strategy1", MockStrategy(), Decimal("0.40"))
        portfolio.add_strategy("strategy2", MockStrategy(), Decimal("0.30"))
        portfolio.add_strategy("strategy3", MockStrategy(), Decimal("0.20"))

        # Total allocated cash should equal sum of strategy cash
        total_strategy_cash = sum(alloc.ledger.cash for alloc in portfolio.strategies.values())

        assert total_strategy_cash == portfolio.allocated_capital
        assert portfolio.allocated_capital == Decimal("90000.00")

    def test_execution_synchronization(self):
        """All strategies process same bar at same timestamp."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add strategies
        strategy1 = MockStrategy()
        strategy2 = MockStrategy()

        portfolio.add_strategy("strategy1", strategy1, Decimal("0.50"))
        portfolio.add_strategy("strategy2", strategy2, Decimal("0.30"))

        # Execute bar
        timestamp = pd.Timestamp("2023-01-01 09:30:00")
        data = {"test": "data"}

        portfolio.execute_bar(timestamp, data)

        # Verify both strategies executed with same data
        assert strategy1.handle_data_called
        assert strategy2.handle_data_called
        assert strategy1.last_data == data
        assert strategy2.last_data == data

        # Verify portfolio timestamp updated
        assert portfolio.current_timestamp == timestamp

    def test_paused_strategy_skipped_during_execution(self):
        """Paused strategies are skipped during bar execution."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        strategy1 = MockStrategy()
        strategy2 = MockStrategy()

        portfolio.add_strategy("strategy1", strategy1, Decimal("0.50"))
        portfolio.add_strategy("strategy2", strategy2, Decimal("0.30"))

        # Pause strategy2
        portfolio.pause_strategy("strategy2")

        # Execute bar
        portfolio.execute_bar(pd.Timestamp("2023-01-01"), {})

        # Only strategy1 should execute
        assert strategy1.handle_data_called
        assert not strategy2.handle_data_called


# Property-Based Tests
class TestPortfolioAllocatorProperties:
    """Property-based tests for portfolio allocator invariants."""

    @given(
        num_strategies=st.integers(min_value=1, max_value=10),
        total_capital=st.decimals(
            min_value=Decimal("1000"), max_value=Decimal("10000000"), places=2
        ),
    )
    def test_capital_always_sums_to_total(self, num_strategies, total_capital):
        """Property: Sum of strategy allocations always equals total allocated capital."""
        portfolio = PortfolioAllocator(total_capital=total_capital)

        # Add strategies with equal allocations (ensuring they sum < 100%)
        allocation_pct = Decimal("0.80") / Decimal(str(num_strategies))

        for i in range(num_strategies):
            portfolio.add_strategy(
                strategy_id=f"strategy_{i}", strategy=MockStrategy(), allocation_pct=allocation_pct
            )

        # Property: Sum of allocated capital equals total allocated
        total_allocated = sum(alloc.allocated_capital for alloc in portfolio.strategies.values())

        assert total_allocated == portfolio.allocated_capital

        # Property: Total allocated <= total capital
        assert portfolio.allocated_capital <= total_capital

    @given(
        initial_alloc=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("0.5"), places=2),
        new_alloc=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("0.5"), places=2),
    )
    def test_rebalancing_preserves_capital(self, initial_alloc, new_alloc):
        """Property: Rebalancing preserves total capital."""
        total_capital = Decimal("100000.00")
        portfolio = PortfolioAllocator(total_capital=total_capital)

        # Add strategy
        portfolio.add_strategy("test", MockStrategy(), initial_alloc)

        # Rebalance
        portfolio.rebalance({"test": new_alloc})

        # Property: Total allocated capital changes but is still valid
        assert portfolio.allocated_capital == total_capital * new_alloc

        # Property: Ledger cash matches allocated capital
        alloc = portfolio.strategies["test"]
        assert alloc.ledger.cash == alloc.allocated_capital

    @given(num_strategies=st.integers(min_value=2, max_value=5))
    def test_no_strategy_interference(self, num_strategies):
        """Property: Strategies cannot interfere with each other's state."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add multiple strategies
        allocation_pct = Decimal("0.15")
        for i in range(num_strategies):
            portfolio.add_strategy(f"strategy_{i}", MockStrategy(), allocation_pct)

        # Modify one strategy's ledger
        first_strategy = list(portfolio.strategies.values())[0]
        first_strategy.ledger.cash = Decimal("999.99")

        # Property: Other strategies unchanged
        for i, (sid, alloc) in enumerate(portfolio.strategies.items()):
            if i == 0:
                assert alloc.ledger.cash == Decimal("999.99")
            else:
                expected_cash = portfolio.total_capital * allocation_pct
                assert alloc.ledger.cash == expected_cash

    @given(num_periods=st.integers(min_value=10, max_value=100))
    def test_portfolio_metrics_consistency(self, num_periods):
        """Property: Portfolio metrics are consistent with strategy metrics."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        portfolio.add_strategy("strategy1", MockStrategy(), Decimal("0.50"))
        portfolio.add_strategy("strategy2", MockStrategy(), Decimal("0.30"))

        # Simulate multiple periods
        for i in range(num_periods):
            timestamp = pd.Timestamp("2023-01-01") + pd.Timedelta(days=i)
            portfolio.execute_bar(timestamp, {})

        # Property: Portfolio value = sum of strategy values
        portfolio_metrics = portfolio.get_portfolio_metrics()
        total_value = sum(alloc.ledger.portfolio_value for alloc in portfolio.strategies.values())

        assert Decimal(portfolio_metrics["total_value"]) == total_value


# Integration Tests
class TestPortfolioAllocatorIntegration:
    """Integration tests for multi-strategy scenarios."""

    def test_three_strategy_portfolio_over_time(self):
        """Integration test: 3-strategy portfolio over 100 days."""
        # Create portfolio
        portfolio = PortfolioAllocator(
            total_capital=Decimal("1000000.00"), name="Diversified Equity Portfolio"
        )

        # Add three strategies
        portfolio.add_strategy(
            "long_equity",
            MockStrategy(),
            Decimal("0.40"),
            metadata={"description": "Long-only large cap growth"},
        )

        portfolio.add_strategy(
            "short_equity",
            MockStrategy(),
            Decimal("0.30"),
            metadata={"description": "Short overvalued momentum stocks"},
        )

        portfolio.add_strategy(
            "market_neutral",
            MockStrategy(),
            Decimal("0.30"),
            metadata={"description": "Beta-neutral long/short value"},
        )

        # Verify initial state
        assert len(portfolio.strategies) == 3
        assert portfolio.allocated_capital == Decimal("1000000.00")

        # Simulate 100 trading days
        start_date = pd.Timestamp("2023-01-01")

        for day in range(100):
            timestamp = start_date + pd.Timedelta(days=day)

            # Mock market data
            data = {
                "AAPL": {"price": Decimal("150.00") + Decimal(str(day * 0.5))},
                "GOOGL": {"price": Decimal("100.00") + Decimal(str(day * 0.3))},
            }

            # Execute bar
            portfolio.execute_bar(timestamp, data)

        # Verify all strategies executed
        for strategy_id, allocation in portfolio.strategies.items():
            assert len(allocation.performance.timestamps) == 100
            assert len(allocation.performance.portfolio_values) == 100

        # Get final metrics
        portfolio_metrics = portfolio.get_portfolio_metrics()
        strategy_metrics = portfolio.get_strategy_metrics()

        # Verify metrics computed
        assert "total_value" in portfolio_metrics
        assert len(strategy_metrics) == 3

        # Each strategy should have performance data
        for strategy_id, metrics in strategy_metrics.items():
            assert "sharpe_ratio" in metrics
            assert "max_drawdown" in metrics
            assert "return_pct" in metrics

    def test_dynamic_add_remove_strategies(self):
        """Integration test: Dynamically add and remove strategies during execution."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Start with one strategy
        portfolio.add_strategy("initial", MockStrategy(), Decimal("0.50"))

        # Run for 30 days
        start_date = pd.Timestamp("2023-01-01")

        for day in range(30):
            timestamp = start_date + pd.Timedelta(days=day)
            portfolio.execute_bar(timestamp, {})

            # Add second strategy on day 10
            if day == 10:
                portfolio.add_strategy("added", MockStrategy(), Decimal("0.30"))
                assert len(portfolio.strategies) == 2

            # Remove first strategy on day 20
            if day == 20:
                portfolio.remove_strategy("initial", liquidate=True)
                assert len(portfolio.strategies) == 1
                assert "added" in portfolio.strategies

        # Verify final state
        assert len(portfolio.strategies) == 1
        final_alloc = portfolio.strategies["added"]
        # Strategy was added on day 10 and ran through day 29 (inclusive) = 19 days
        assert len(final_alloc.performance.timestamps) == 19

    def test_rebalancing_with_performance_based_allocation(self):
        """Integration test: Rebalance based on strategy performance."""
        portfolio = PortfolioAllocator(total_capital=Decimal("100000.00"))

        # Add two strategies
        portfolio.add_strategy("winner", MockStrategy(), Decimal("0.30"))
        portfolio.add_strategy("loser", MockStrategy(), Decimal("0.30"))

        # Simulate performance (winner gains 20%, loser loses 10%)
        winner = portfolio.strategies["winner"]
        loser = portfolio.strategies["loser"]

        # Simulate value changes
        winner.ledger.cash = Decimal("36000.00")  # +20%
        loser.ledger.cash = Decimal("27000.00")  # -10%

        # Rebalance: allocate more to winner
        portfolio.rebalance(
            {"winner": Decimal("0.50"), "loser": Decimal("0.20")},  # Increase from 30% to 50%
            reason="Performance-based rebalancing",
        )  # Decrease from 30% to 20%

        # Verify new allocations
        assert winner.allocated_capital == Decimal("50000.00")
        assert loser.allocated_capital == Decimal("20000.00")


class TestStrategyPerformance:
    """Test StrategyPerformance tracking."""

    def test_performance_metrics_calculation(self):
        """Test performance metrics are calculated correctly."""
        perf = StrategyPerformance("test_strategy", lookback_window=252)

        # Add some observations
        timestamps = [pd.Timestamp("2023-01-01") + pd.Timedelta(days=i) for i in range(10)]
        values = [
            Decimal("100000"),
            Decimal("101000"),
            Decimal("102000"),
            Decimal("101500"),
            Decimal("103000"),
            Decimal("104000"),
            Decimal("103500"),
            Decimal("105000"),
            Decimal("106000"),
            Decimal("107000"),
        ]

        for ts, val in zip(timestamps, values, strict=False):
            perf.update(ts, val)

        # Verify data stored
        assert len(perf.timestamps) == 10
        assert len(perf.portfolio_values) == 10
        assert len(perf.returns) == 9  # One less than values

        # Verify metrics calculated
        assert perf.volatility >= Decimal("0")
        assert perf.mean_return != Decimal("0")
        metrics = perf.get_metrics()
        assert metrics["num_observations"] == 10

    def test_drawdown_calculation(self):
        """Test drawdown metrics are calculated correctly."""
        perf = StrategyPerformance("test_strategy")

        # Create a series with drawdown
        values = [
            Decimal("100000"),
            Decimal("110000"),  # New peak
            Decimal("105000"),  # 4.5% drawdown
            Decimal("100000"),  # 9.1% drawdown
            Decimal("115000"),  # New peak
        ]

        timestamps = [pd.Timestamp("2023-01-01") + pd.Timedelta(days=i) for i in range(5)]

        for ts, val in zip(timestamps, values, strict=False):
            perf.update(ts, val)

        # Peak should be 115000
        assert perf.peak_value == Decimal("115000")

        # Max drawdown should be negative (worst drop)
        assert perf.max_drawdown < Decimal("0")

    def test_win_rate_and_profit_factor(self):
        """Test win rate and profit factor calculation."""
        perf = StrategyPerformance("test_strategy")

        # Create series with known win/loss pattern
        values = [
            Decimal("100000"),
            Decimal("105000"),  # Win
            Decimal("103000"),  # Loss
            Decimal("108000"),  # Win
            Decimal("106000"),  # Loss
        ]

        timestamps = [pd.Timestamp("2023-01-01") + pd.Timedelta(days=i) for i in range(5)]

        for ts, val in zip(timestamps, values, strict=False):
            perf.update(ts, val)

        # Should have 2 wins, 2 losses
        assert perf.winning_periods == 2
        assert perf.losing_periods == 2
        assert perf.win_rate == Decimal("0.5")

        # Profit factor should be calculated
        assert perf.profit_factor > Decimal("0")
