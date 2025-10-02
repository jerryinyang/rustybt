"""Comprehensive tests for portfolio risk management.

Tests cover:
- Leverage limit enforcement
- Concentration limit enforcement
- Drawdown limit enforcement
- Volatility targeting
- VaR calculation (Historical Simulation)
- Correlation matrix calculation
- Portfolio beta calculation
- Risk alert triggering
- Trading halt mechanism
- Position aggregation logic
- Limit violation logging
- Edge cases (zero volatility, single strategy)
- Property-based tests
- Integration tests
"""

from decimal import Decimal

import numpy as np
import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition
from rustybt.portfolio.risk import (
    RiskAction,
    RiskLimits,
    RiskLimitType,
    RiskManager,
    create_hedge_fund_risk_config,
)

# =======================
# Test Fixtures
# =======================


class MockAsset:
    """Mock asset for testing."""

    def __init__(self, symbol: str, exchange: str):
        self.symbol = symbol
        self.exchange = exchange

    def __hash__(self):
        return hash((self.symbol, self.exchange))

    def __eq__(self, other):
        if not isinstance(other, MockAsset):
            return False
        return self.symbol == other.symbol and self.exchange == other.exchange


class MockOrder:
    """Mock order for testing."""

    def __init__(
        self,
        asset: MockAsset,
        amount: Decimal,
        estimated_fill_price: Decimal,
        order_id: str = "order-1",
    ):
        self.id = order_id
        self.asset = asset
        self.amount = amount
        self.estimated_fill_price = estimated_fill_price


class MockStrategyAllocation:
    """Mock strategy allocation for testing."""

    def __init__(
        self,
        allocated_capital: Decimal,
        returns: list[Decimal],
        peak_value: Decimal,
        max_drawdown: Decimal,
    ):
        self.allocated_capital = allocated_capital
        self.ledger = DecimalLedger(starting_cash=allocated_capital)
        self.performance = MockPerformance(returns, peak_value, max_drawdown)


class MockPerformance:
    """Mock performance tracker."""

    def __init__(self, returns: list[Decimal], peak_value: Decimal, max_drawdown: Decimal):
        self.returns = returns
        self.peak_value = peak_value
        self.max_drawdown = max_drawdown


class MockPortfolio:
    """Mock portfolio for testing."""

    def __init__(self, total_capital: Decimal):
        self.total_capital = total_capital
        self.strategies: dict[str, MockStrategyAllocation] = {}

    def get_total_portfolio_value(self) -> Decimal:
        """Calculate total portfolio value."""
        total = Decimal("0")
        for strategy_alloc in self.strategies.values():
            total += strategy_alloc.ledger.portfolio_value
        return total

    def add_strategy(
        self,
        strategy_id: str,
        allocated_capital: Decimal,
        returns: list[Decimal],
        peak_value: Decimal,
        max_drawdown: Decimal,
    ):
        """Add mock strategy."""
        self.strategies[strategy_id] = MockStrategyAllocation(
            allocated_capital, returns, peak_value, max_drawdown
        )


# =======================
# Unit Tests
# =======================


def test_leverage_limit_enforcement():
    """Leverage limit rejects orders exceeding limit."""
    limits = RiskLimits(
        max_portfolio_leverage=Decimal("2.0"),
        warn_portfolio_leverage=Decimal("1.5"),
        max_single_asset_exposure=Decimal("10.0"),  # Disable concentration check
    )
    risk_mgr = RiskManager(limits)

    # Create portfolio with $100k equity
    portfolio = MockPortfolio(total_capital=Decimal("100000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("100000.00"),
        returns=[],
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("0"),
    )

    # Add existing position
    # Portfolio value = $100k cash + $15k position = $115k
    # Current exposure = $15k
    # Current leverage = $15k / $115k = 0.13x
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    position = DecimalPosition(
        asset=asset,
        amount=Decimal("100"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
        last_sale_date=pd.Timestamp("2023-01-01"),
    )
    portfolio.strategies["strategy1"].ledger.positions[asset] = position

    # Order that would push leverage over 2.0x
    # New exposure = $15k + $300k = $315k
    # New leverage = $315k / $115k = 2.74x > 2.0x
    order = MockOrder(asset=asset, amount=Decimal("2000"), estimated_fill_price=Decimal("150.00"))
    current_prices = {"AAPL": Decimal("150.00")}

    # Check order
    allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

    # Should reject
    assert not allowed
    assert action == RiskAction.REJECT
    assert "Leverage limit exceeded" in reason


def test_leverage_warning_level():
    """Leverage warning issued when approaching limit."""
    limits = RiskLimits(
        max_portfolio_leverage=Decimal("2.0"),
        warn_portfolio_leverage=Decimal("1.5"),
        max_single_asset_exposure=Decimal("10.0"),  # Disable concentration check
    )
    risk_mgr = RiskManager(limits)

    # Create portfolio
    portfolio = MockPortfolio(total_capital=Decimal("100000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("100000.00"),
        returns=[],
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("0"),
    )

    # Order that pushes leverage to 1.6x (exceeds 1.5x warning, but not 2.0x limit)
    # Portfolio value = $100k
    # Order exposure = 1000 * $160 = $160k
    # New leverage = $160k / $100k = 1.6x
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    order = MockOrder(asset=asset, amount=Decimal("1000"), estimated_fill_price=Decimal("160.00"))
    current_prices = {}

    # Check order
    allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

    # Should warn but allow
    assert allowed
    assert action == RiskAction.WARN
    assert "Leverage warning" in reason


def test_concentration_limit_enforcement():
    """Concentration limit rejects orders exceeding single asset limit."""
    limits = RiskLimits(
        max_single_asset_exposure=Decimal("0.20"),  # 20% max
        warn_single_asset_exposure=Decimal("0.15"),  # 15% warning
    )
    risk_mgr = RiskManager(limits)

    # Create portfolio with $100k
    portfolio = MockPortfolio(total_capital=Decimal("100000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("100000.00"),
        returns=[],
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("0"),
    )

    # Add existing AAPL position (15% exposure = $15k)
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    position = DecimalPosition(
        asset=asset,
        amount=Decimal("100"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
        last_sale_date=pd.Timestamp("2023-01-01"),
    )
    portfolio.strategies["strategy1"].ledger.positions[asset] = position

    # Order that would push AAPL to 25% (exceeds 20% limit)
    # Current: $15k / $100k = 15%
    # Order: $10k more
    # New: $25k / $100k = 25% > 20%
    order = MockOrder(asset=asset, amount=Decimal("100"), estimated_fill_price=Decimal("100.00"))
    current_prices = {"AAPL": Decimal("150.00")}

    # Check order
    allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

    # Should reject
    assert not allowed
    assert action == RiskAction.REJECT
    assert "Concentration limit exceeded" in reason


def test_drawdown_limit_enforcement():
    """Drawdown limit rejects orders when in max drawdown."""
    limits = RiskLimits(
        max_drawdown=Decimal("0.15"),  # 15% max
        warn_drawdown=Decimal("0.10"),  # 10% warning
        halt_drawdown=Decimal("0.20"),  # 20% halt
    )
    risk_mgr = RiskManager(limits)

    # Create portfolio with 16% drawdown (exceeds 15% limit)
    # Peak: $100k, Current: $84k = -16%
    portfolio = MockPortfolio(total_capital=Decimal("84000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("84000.00"),
        returns=[],
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("-0.16"),
    )

    # Create order
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    order = MockOrder(asset=asset, amount=Decimal("10"), estimated_fill_price=Decimal("100.00"))
    current_prices = {}

    # Check order
    allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

    # Should reject
    assert not allowed
    assert action == RiskAction.REJECT
    assert "Drawdown limit exceeded" in reason


def test_trading_halt_mechanism():
    """Trading halt prevents all orders after critical drawdown."""
    limits = RiskLimits(halt_drawdown=Decimal("0.20"))  # 20% halt threshold
    risk_mgr = RiskManager(limits)

    # Create portfolio with 21% drawdown (exceeds halt threshold)
    # Peak: $100k, Current: $79k = -21%
    portfolio = MockPortfolio(total_capital=Decimal("79000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("79000.00"),
        returns=[],
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("-0.21"),
    )

    # First order triggers halt
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    order1 = MockOrder(asset=asset, amount=Decimal("10"), estimated_fill_price=Decimal("100.00"))
    allowed, action, reason = risk_mgr.check_order(portfolio, order1, {})

    assert not allowed
    assert action == RiskAction.HALT
    assert limits.trading_halted

    # Subsequent orders also rejected (halted state)
    order2 = MockOrder(asset=asset, amount=Decimal("5"), estimated_fill_price=Decimal("100.00"))
    allowed, action, reason = risk_mgr.check_order(portfolio, order2, {})

    assert not allowed
    assert action == RiskAction.HALT
    assert "Trading halted" in reason


def test_volatility_targeting_calculation():
    """Volatility targeting adjusts allocations to maintain target."""
    limits = RiskLimits(target_volatility=Decimal("0.12"))  # 12% target
    risk_mgr = RiskManager(limits)

    # Create portfolio with known volatility
    # Returns with 15% annualized volatility (too high)
    np.random.seed(42)
    daily_std = 0.15 / np.sqrt(252)  # Daily std from 15% annual
    returns = [Decimal(str(x)) for x in np.random.normal(0, daily_std, 100)]

    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("500000.00"),
        returns=returns,
        peak_value=Decimal("500000.00"),
        max_drawdown=Decimal("0"),
    )
    portfolio.add_strategy(
        "strategy2",
        allocated_capital=Decimal("500000.00"),
        returns=returns,
        peak_value=Decimal("500000.00"),
        max_drawdown=Decimal("0"),
    )

    current_allocations = {"strategy1": Decimal("0.50"), "strategy2": Decimal("0.50")}

    # Apply volatility targeting
    adjusted = risk_mgr.apply_volatility_targeting(portfolio, current_allocations)

    # Should still sum to 1.0 after normalization
    assert abs(sum(adjusted.values()) - Decimal("1.0")) < Decimal("0.0001")

    # Ratios should be preserved
    expected_ratio = current_allocations["strategy1"] / current_allocations["strategy2"]
    actual_ratio = adjusted["strategy1"] / adjusted["strategy2"]
    assert abs(expected_ratio - actual_ratio) < Decimal("0.01")


def test_var_calculation_historical_simulation():
    """VaR calculation using Historical Simulation method."""
    risk_mgr = RiskManager()

    # Create portfolio with known return distribution
    # Normal distribution: mean=0, std=2%
    np.random.seed(42)
    returns = [Decimal(str(x)) for x in np.random.normal(0, 0.02, 252)]

    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("1000000.00"),
        returns=returns,
        peak_value=Decimal("1000000.00"),
        max_drawdown=Decimal("0"),
    )

    portfolio_value = Decimal("1000000.00")

    # Calculate 95% VaR
    var_95 = risk_mgr.calculate_var(portfolio, Decimal("0.95"), portfolio_value)

    # VaR should be positive (represents potential loss)
    assert var_95 > Decimal("0")

    # For 95% confidence, VaR should be reasonable
    # With 2% daily std, 5th percentile ≈ -3.3%
    # VaR ≈ 3.3% × $1M = $33,000
    # Allow some variance due to random generation
    assert Decimal("20000") < var_95 < Decimal("50000")


def test_var_increases_with_confidence():
    """VaR increases with higher confidence level."""
    risk_mgr = RiskManager()

    # Create portfolio
    np.random.seed(42)
    returns = [Decimal(str(x)) for x in np.random.normal(0, 0.02, 252)]

    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("1000000.00"),
        returns=returns,
        peak_value=Decimal("1000000.00"),
        max_drawdown=Decimal("0"),
    )

    portfolio_value = Decimal("1000000.00")

    # Calculate VaR at different confidence levels
    var_90 = risk_mgr.calculate_var(portfolio, Decimal("0.90"), portfolio_value)
    var_95 = risk_mgr.calculate_var(portfolio, Decimal("0.95"), portfolio_value)
    var_99 = risk_mgr.calculate_var(portfolio, Decimal("0.99"), portfolio_value)

    # Higher confidence should have higher VaR
    assert var_99 >= var_95
    assert var_95 >= var_90


def test_correlation_matrix_calculation():
    """Correlation matrix calculation using Polars."""
    risk_mgr = RiskManager()

    # Create portfolio with known correlations
    # Strategy 1 and 2: highly correlated
    # Strategy 3: less correlated
    np.random.seed(42)
    base_returns = np.random.normal(0.001, 0.01, 100)
    returns_s1 = [Decimal(str(x)) for x in base_returns]
    returns_s2 = [
        Decimal(str(x + np.random.normal(0, 0.001))) for x in base_returns
    ]  # Similar to s1
    returns_s3 = [Decimal(str(x)) for x in np.random.normal(0, 0.01, 100)]  # Independent

    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "s1",
        allocated_capital=Decimal("333333.00"),
        returns=returns_s1,
        peak_value=Decimal("333333.00"),
        max_drawdown=Decimal("0"),
    )
    portfolio.add_strategy(
        "s2",
        allocated_capital=Decimal("333333.00"),
        returns=returns_s2,
        peak_value=Decimal("333333.00"),
        max_drawdown=Decimal("0"),
    )
    portfolio.add_strategy(
        "s3",
        allocated_capital=Decimal("333334.00"),
        returns=returns_s3,
        peak_value=Decimal("333334.00"),
        max_drawdown=Decimal("0"),
    )

    # Calculate correlation matrix
    corr_matrix = risk_mgr.calculate_correlation_matrix(portfolio)

    # Should be 3x3 matrix
    assert corr_matrix is not None
    assert corr_matrix.shape == (3, 3)

    # Diagonal should be 1.0
    assert abs(corr_matrix.iloc[0, 0] - 1.0) < 0.01
    assert abs(corr_matrix.iloc[1, 1] - 1.0) < 0.01
    assert abs(corr_matrix.iloc[2, 2] - 1.0) < 0.01

    # s1 and s2 should be highly correlated (since s2 is based on s1)
    assert corr_matrix.iloc[0, 1] > 0.90


def test_correlation_matrix_symmetric():
    """Correlation matrix is symmetric."""
    risk_mgr = RiskManager()

    # Create portfolio with multiple strategies
    np.random.seed(42)
    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))

    for i in range(3):
        returns = [Decimal(str(x)) for x in np.random.normal(0, 0.01, 100)]
        portfolio.add_strategy(
            f"strategy_{i}",
            allocated_capital=Decimal("333333.00"),
            returns=returns,
            peak_value=Decimal("333333.00"),
            max_drawdown=Decimal("0"),
        )

    # Calculate correlation matrix
    corr_matrix = risk_mgr.calculate_correlation_matrix(portfolio)

    if corr_matrix is not None:
        # Should be symmetric
        assert np.allclose(corr_matrix.values, corr_matrix.values.T, rtol=1e-10)


def test_portfolio_beta_calculation():
    """Portfolio beta calculation against market index."""
    risk_mgr = RiskManager()

    # Create portfolio returns that move with market
    # β ≈ 1.5 (portfolio 50% more volatile than market)
    np.random.seed(42)
    market_returns = [Decimal(str(x)) for x in np.random.normal(0.001, 0.01, 100)]
    portfolio_returns = [r * Decimal("1.5") for r in market_returns]

    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("1000000.00"),
        returns=portfolio_returns,
        peak_value=Decimal("1000000.00"),
        max_drawdown=Decimal("0"),
    )

    # Calculate beta
    beta = risk_mgr._calculate_portfolio_beta(portfolio, market_returns)

    # Beta should be approximately 1.5
    assert Decimal("1.3") < beta < Decimal("1.7")


def test_position_aggregation_across_strategies():
    """Position aggregation across strategies for concentration."""
    risk_mgr = RiskManager()

    # Create portfolio with AAPL positions in multiple strategies
    portfolio = MockPortfolio(total_capital=Decimal("100000.00"))

    # Strategy 1: 100 shares AAPL
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("50000.00"),
        returns=[],
        peak_value=Decimal("50000.00"),
        max_drawdown=Decimal("0"),
    )
    position1 = DecimalPosition(
        asset=asset,
        amount=Decimal("100"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
        last_sale_date=pd.Timestamp("2023-01-01"),
    )
    portfolio.strategies["strategy1"].ledger.positions[asset] = position1

    # Strategy 2: 50 shares AAPL
    portfolio.add_strategy(
        "strategy2",
        allocated_capital=Decimal("50000.00"),
        returns=[],
        peak_value=Decimal("50000.00"),
        max_drawdown=Decimal("0"),
    )
    position2 = DecimalPosition(
        asset=asset,
        amount=Decimal("50"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
        last_sale_date=pd.Timestamp("2023-01-01"),
    )
    portfolio.strategies["strategy2"].ledger.positions[asset] = position2

    current_prices = {"AAPL": Decimal("150.00")}
    total_equity = Decimal("100000.00")

    # Calculate concentration
    # Total: 150 shares × $150 = $22,500 / $100,000 = 22.5%
    max_exposure, max_symbol = risk_mgr._calculate_max_concentration(
        portfolio, current_prices, total_equity
    )

    assert max_symbol == "AAPL"
    assert abs(max_exposure - Decimal("0.225")) < Decimal("0.001")


def test_limit_violation_tracking():
    """Limit violations are tracked."""
    limits = RiskLimits(max_portfolio_leverage=Decimal("2.0"))
    risk_mgr = RiskManager(limits)

    # Create portfolio
    portfolio = MockPortfolio(total_capital=Decimal("100000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("100000.00"),
        returns=[],
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("0"),
    )

    # Trigger violation
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    order = MockOrder(asset=asset, amount=Decimal("2000"), estimated_fill_price=Decimal("150.00"))
    current_prices = {}

    # Initial violation count should be 0
    assert risk_mgr.violation_count[RiskLimitType.LEVERAGE] == 0

    # Check order (should trigger violation)
    allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

    # Verify violation tracked
    assert risk_mgr.violation_count[RiskLimitType.LEVERAGE] > 0


def test_edge_case_zero_volatility():
    """Handle edge case: strategy with zero volatility."""
    risk_mgr = RiskManager()

    # Create portfolio with zero volatility (constant returns)
    returns = [Decimal("0.01")] * 100  # All same
    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("1000000.00"),
        returns=returns,
        peak_value=Decimal("1000000.00"),
        max_drawdown=Decimal("0"),
    )

    # Calculate volatility (should handle gracefully)
    vol = risk_mgr._calculate_portfolio_volatility(portfolio)

    # Should return very low volatility (or zero)
    assert vol >= Decimal("0")
    assert vol < Decimal("0.001")


def test_edge_case_single_strategy():
    """Handle edge case: portfolio with single strategy."""
    risk_mgr = RiskManager()

    # Create portfolio with only one strategy
    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("1000000.00"),
        returns=[Decimal("0.01")] * 100,
        peak_value=Decimal("1000000.00"),
        max_drawdown=Decimal("0"),
    )

    # Calculate correlation matrix (should return None)
    corr_matrix = risk_mgr.calculate_correlation_matrix(portfolio)

    assert corr_matrix is None


def test_edge_case_insufficient_data():
    """Handle edge case: insufficient data for VaR."""
    risk_mgr = RiskManager()

    # Create portfolio with very few returns
    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("1000000.00"),
        returns=[Decimal("0.01"), Decimal("0.02")],  # Only 2 returns
        peak_value=Decimal("1000000.00"),
        max_drawdown=Decimal("0"),
    )

    # Calculate VaR (should handle gracefully)
    var_95 = risk_mgr.calculate_var(portfolio, Decimal("0.95"), Decimal("1000000.00"))

    # Should return 0 for insufficient data
    assert var_95 == Decimal("0")


def test_metrics_calculation():
    """Risk metrics calculation includes all required fields."""
    risk_mgr = RiskManager()

    # Create portfolio
    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    np.random.seed(42)
    returns = [Decimal(str(x)) for x in np.random.normal(0.001, 0.01, 100)]

    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("1000000.00"),
        returns=returns,
        peak_value=Decimal("1000000.00"),
        max_drawdown=Decimal("-0.05"),
    )

    current_prices = {}
    market_returns = [Decimal(str(x)) for x in np.random.normal(0.001, 0.01, 100)]

    # Calculate metrics
    metrics = risk_mgr.calculate_metrics(portfolio, current_prices, market_returns)

    # Verify all fields populated
    assert isinstance(metrics.timestamp, pd.Timestamp)
    assert metrics.total_exposure >= Decimal("0")
    assert metrics.total_equity > Decimal("0")
    assert metrics.leverage >= Decimal("0")
    assert metrics.max_asset_exposure >= Decimal("0")
    assert metrics.portfolio_volatility >= Decimal("0")
    assert metrics.var_95 >= Decimal("0")
    assert metrics.var_99 >= Decimal("0")
    assert metrics.portfolio_beta is not None


def test_hedge_fund_config_creation():
    """Hedge fund risk configuration is created correctly."""
    limits = create_hedge_fund_risk_config()

    # Verify conservative limits
    assert limits.max_portfolio_leverage == Decimal("1.5")
    assert limits.max_single_asset_exposure == Decimal("0.10")
    assert limits.max_drawdown == Decimal("0.12")
    assert limits.target_volatility == Decimal("0.10")


# =======================
# Property-Based Tests
# =======================


@given(leverage=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("5.0"), places=2))
def test_property_limits_always_enforced(leverage):
    """Property: Leverage limits always enforced."""
    limits = RiskLimits(max_portfolio_leverage=Decimal("2.0"))
    risk_mgr = RiskManager(limits)

    # Create portfolio with given leverage
    portfolio = MockPortfolio(total_capital=Decimal("100000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("100000.00"),
        returns=[],
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("0"),
    )

    # Add position to achieve target leverage
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    if leverage > Decimal("0"):
        exposure = leverage * Decimal("100000.00")
        shares = exposure / Decimal("150.00")
        position = DecimalPosition(
            asset=asset,
            amount=shares,
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
            last_sale_date=pd.Timestamp("2023-01-01"),
        )
        portfolio.strategies["strategy1"].ledger.positions[asset] = position

    # Check order with no new exposure
    order = MockOrder(asset=asset, amount=Decimal("0"), estimated_fill_price=Decimal("150.00"))

    allowed, action, reason = risk_mgr.check_order(portfolio, order, {})

    # If leverage exceeds limit, should reject
    if leverage > Decimal("2.0"):
        assert not allowed or action != RiskAction.ALLOW


@given(num_periods=st.integers(min_value=10, max_value=252))
def test_property_volatility_non_negative(num_periods):
    """Property: Volatility is always non-negative."""
    risk_mgr = RiskManager()

    # Create portfolio with random returns
    np.random.seed(42)
    returns = [Decimal(str(x)) for x in np.random.normal(0, 0.02, num_periods)]

    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))
    portfolio.add_strategy(
        "strategy1",
        allocated_capital=Decimal("1000000.00"),
        returns=returns,
        peak_value=Decimal("1000000.00"),
        max_drawdown=Decimal("0"),
    )

    # Calculate volatility
    vol = risk_mgr._calculate_portfolio_volatility(portfolio)

    # Should be non-negative
    assert vol >= Decimal("0")


@given(num_strategies=st.integers(min_value=2, max_value=5))
def test_property_correlation_bounded(num_strategies):
    """Property: Correlation values in [-1, 1] range."""
    risk_mgr = RiskManager()

    # Create portfolio
    np.random.seed(42)
    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))

    for i in range(num_strategies):
        returns = [Decimal(str(x)) for x in np.random.normal(0, 0.01, 100)]
        portfolio.add_strategy(
            f"strategy_{i}",
            allocated_capital=Decimal("333333.00"),
            returns=returns,
            peak_value=Decimal("333333.00"),
            max_drawdown=Decimal("0"),
        )

    # Calculate correlation matrix
    corr_matrix = risk_mgr.calculate_correlation_matrix(portfolio)

    if corr_matrix is not None:
        # All correlations should be in [-1, 1]
        assert (corr_matrix.values >= -1.0).all()
        assert (corr_matrix.values <= 1.0).all()


# =======================
# Integration Tests
# =======================


def test_integration_full_risk_management():
    """Integration test: Full risk management with multiple strategies."""
    # Create portfolio
    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))

    # Add strategies
    np.random.seed(42)
    for i in range(3):
        returns = [Decimal(str(x)) for x in np.random.normal(0.001, 0.01, 100)]
        portfolio.add_strategy(
            f"strategy{i}",
            allocated_capital=Decimal("333333.00"),
            returns=returns,
            peak_value=Decimal("333333.00"),
            max_drawdown=Decimal("-0.05"),
        )

    # Create risk manager
    limits = RiskLimits(
        max_portfolio_leverage=Decimal("2.0"),
        max_single_asset_exposure=Decimal("0.20"),
        max_drawdown=Decimal("0.15"),
    )
    risk_mgr = RiskManager(limits)

    # Calculate metrics
    current_prices = {}
    metrics = risk_mgr.calculate_metrics(portfolio, current_prices)

    # Verify metrics
    assert metrics.leverage >= Decimal("0")
    assert Decimal("0") <= metrics.max_asset_exposure <= Decimal("1.0")
    assert metrics.portfolio_volatility >= Decimal("0")
    assert metrics.var_95 >= Decimal("0")

    # Check order
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    order = MockOrder(asset=asset, amount=Decimal("100"), estimated_fill_price=Decimal("150.00"))
    allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

    # Should be allowed (within limits)
    assert allowed


def test_integration_volatility_targeting():
    """Integration test: Volatility targeting adjusts allocations."""
    # Create portfolio
    portfolio = MockPortfolio(total_capital=Decimal("1000000.00"))

    # Add strategies with different volatilities
    np.random.seed(42)
    high_vol_returns = [Decimal(str(x)) for x in np.random.normal(0.001, 0.02, 100)]
    low_vol_returns = [Decimal(str(x)) for x in np.random.normal(0.001, 0.005, 100)]

    portfolio.add_strategy(
        "high_vol",
        allocated_capital=Decimal("500000.00"),
        returns=high_vol_returns,
        peak_value=Decimal("500000.00"),
        max_drawdown=Decimal("0"),
    )
    portfolio.add_strategy(
        "low_vol",
        allocated_capital=Decimal("500000.00"),
        returns=low_vol_returns,
        peak_value=Decimal("500000.00"),
        max_drawdown=Decimal("0"),
    )

    # Risk manager with volatility targeting
    limits = RiskLimits(target_volatility=Decimal("0.12"))  # 12% target
    risk_mgr = RiskManager(limits)

    # Apply volatility targeting
    current_allocations = {"high_vol": Decimal("0.50"), "low_vol": Decimal("0.50")}

    adjusted = risk_mgr.apply_volatility_targeting(portfolio, current_allocations)

    # Should sum to 1.0
    assert abs(sum(adjusted.values()) - Decimal("1.0")) < Decimal("0.0001")


def test_integration_limit_violations_prevent_orders():
    """Integration test: Limit violations prevent order execution."""
    portfolio = MockPortfolio(total_capital=Decimal("100000.00"))
    portfolio.add_strategy(
        "aggressive",
        allocated_capital=Decimal("100000.00"),
        returns=[],
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("0"),
    )

    # Strict limits
    limits = RiskLimits(
        max_portfolio_leverage=Decimal("1.5"), max_single_asset_exposure=Decimal("0.15")
    )
    risk_mgr = RiskManager(limits)

    # Large order that would violate limits
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    order = MockOrder(asset=asset, amount=Decimal("2000"), estimated_fill_price=Decimal("100.00"))
    current_prices = {}

    # Check order
    allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

    # Should reject due to leverage
    assert not allowed
    assert risk_mgr.violation_count[RiskLimitType.LEVERAGE] > 0


def test_integration_drawdown_halt():
    """Integration test: Excessive drawdown triggers halt."""
    portfolio = MockPortfolio(total_capital=Decimal("79000.00"))

    # Strategy with excessive drawdown
    portfolio.add_strategy(
        "loser",
        allocated_capital=Decimal("79000.00"),
        returns=[Decimal("-0.01")] * 50,
        peak_value=Decimal("100000.00"),
        max_drawdown=Decimal("-0.21"),
    )

    # Risk manager with halt threshold
    limits = RiskLimits(halt_drawdown=Decimal("0.20"))  # 20% halt
    risk_mgr = RiskManager(limits)

    # Check order (should trigger halt)
    asset = MockAsset(symbol="AAPL", exchange="NASDAQ")
    order = MockOrder(asset=asset, amount=Decimal("10"), estimated_fill_price=Decimal("100.00"))
    allowed, action, reason = risk_mgr.check_order(portfolio, order, {})

    # Should halt
    assert not allowed
    assert action == RiskAction.HALT
    assert limits.trading_halted
