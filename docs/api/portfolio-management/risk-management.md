# Portfolio Risk Management

**Source File**: `/rustybt/portfolio/risk.py` (1,036 lines)

**Last Verified**: 2025-10-16

---

## Overview

RustyBT's risk management system provides **institutional-grade** portfolio-level risk controls including:

- **Pre-Trade Risk Checks**: Leverage, concentration, drawdown limits
- **Real-Time Metrics**: VaR, beta, correlation, volatility
- **Limit Enforcement**: Warn, reduce, reject, or halt trading
- **Volatility Targeting**: Dynamic allocation adjustment
- **Risk Attribution**: Per-strategy and portfolio-level metrics

This documentation covers the complete risk management system with all APIs verified against source code.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [RiskLimits Configuration](#risklimits-configuration)
3. [RiskManager - Main System](#riskmanager-main-system)
4. [Pre-Trade Risk Checks](#pre-trade-risk-checks)
5. [Real-Time Risk Metrics](#real-time-risk-metrics)
6. [Value at Risk (VaR)](#value-at-risk-var)
7. [Volatility Targeting](#volatility-targeting)
8. [Production Examples](#production-examples)
9. [Best Practices](#best-practices)

---

## Core Concepts

### Risk Management Flow

```
Pre-Trade (before order):
┌─────────────────────────┐
│ Check Leverage Limit    │ → max 2.0x
│ Check Concentration     │ → max 20% per asset
│ Check Drawdown Limit    │ → halt if > 20%
└─────────┬───────────────┘
          │
    ┌─────▼──────┐
    │   ALLOW    │
    │   WARN     │
    │   REJECT   │
    │   HALT     │
    └────────────┘

Post-Trade (after bar):
- Calculate leverage, concentration, drawdown
- Calculate volatility, VaR, beta
- Check limit violations
- Log metrics
```

### Risk Limit Types

**Source**: `risk.py:25-34`

```python
class RiskLimitType(Enum):
    """Types of risk limits."""
    LEVERAGE = "leverage"
    CONCENTRATION = "concentration"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    VAR = "var"
    CORRELATION = "correlation"
```

### Risk Actions

**Source**: `risk.py:36-44`

```python
class RiskAction(Enum):
    """Actions taken on risk limit violations."""
    ALLOW = "allow"      # No violation
    WARN = "warn"        # Warning level
    REDUCE = "reduce"    # Reduce position
    REJECT = "reject"    # Reject order
    HALT = "halt"        # Halt trading
```

---

## RiskLimits Configuration

**Source**: `risk.py:46-101`

### Class Definition

```python
@dataclass
class RiskLimits:
    """Risk limit configuration.

    Hedge Fund Style Limits:
    - Max Leverage: 2.0x (conservative) to 6.0x (aggressive)
    - Max Single Asset: 15-25% of portfolio
    - Max Drawdown: 15-20% from peak
    - Target Volatility: 10-15% annualized
    - Max VaR (95%): 3-5% of portfolio
    """

    # Leverage limits
    max_portfolio_leverage: Decimal = Decimal("2.0")
    warn_portfolio_leverage: Decimal = Decimal("1.8")

    # Concentration limits
    max_single_asset_exposure: Decimal = Decimal("0.20")
    warn_single_asset_exposure: Decimal = Decimal("0.15")

    # Drawdown limits
    max_drawdown: Decimal = Decimal("0.15")
    warn_drawdown: Decimal = Decimal("0.10")
    halt_drawdown: Decimal = Decimal("0.20")

    # Volatility limits
    target_volatility: Decimal | None = Decimal("0.12")
    max_volatility: Decimal | None = Decimal("0.20")

    # VaR limits
    max_var_pct: Decimal = Decimal("0.05")
    var_confidence_level: Decimal = Decimal("0.95")

    # Correlation limits
    max_strategy_correlation: Decimal = Decimal("0.80")

    # Trading halt flag
    trading_halted: bool = False
```

### Example 1: Conservative Fund Limits

```python
from decimal import Decimal
from rustybt.portfolio.risk import RiskLimits

# Conservative long-only equity fund
limits = RiskLimits(
    max_portfolio_leverage=Decimal("1.5"),
    max_single_asset_exposure=Decimal("0.10"),  # 10% max
    max_drawdown=Decimal("0.12"),
    target_volatility=Decimal("0.10"),
    max_var_pct=Decimal("0.03"),
)
```

### Example 2: Aggressive Fund Limits

```python
# Aggressive multi-strategy fund
limits = RiskLimits(
    max_portfolio_leverage=Decimal("4.0"),
    max_single_asset_exposure=Decimal("0.25"),  # 25% max
    max_drawdown=Decimal("0.20"),
    target_volatility=Decimal("0.20"),
    max_var_pct=Decimal("0.08"),
)
```

### Helper Function

**Source**: `risk.py:991-1036`

```python
from rustybt.portfolio.risk import create_hedge_fund_risk_config

# Create conservative hedge fund limits
limits = create_hedge_fund_risk_config()
# Returns RiskLimits with 1.5x leverage, 10% concentration, 12% drawdown
```

---

## RiskManager - Main System

**Source**: `risk.py:168-989`

### Constructor

**Source**: `risk.py:234-256`

```python
class RiskManager:
    """Portfolio-level risk manager."""

    def __init__(
        self,
        limits: RiskLimits | None = None,
        lookback_window: int = 252,
    ):
        """Initialize risk manager.

        Args:
            limits: Risk limits (defaults if None)
            lookback_window: Periods for metrics (252 = 1 year)
        """
```

### Example 3: Basic Setup

```python
from rustybt.portfolio.risk import RiskManager, RiskLimits
from rustybt.portfolio.allocator import PortfolioAllocator

# Create risk manager
risk_mgr = RiskManager(
    limits=RiskLimits(
        max_portfolio_leverage=Decimal("2.0"),
        max_single_asset_exposure=Decimal("0.15"),
    ),
    lookback_window=252,
)

# Create portfolio
portfolio = PortfolioAllocator(total_capital=Decimal("1000000"))
```

---

## Pre-Trade Risk Checks

### check_order()

**Source**: `risk.py:258-313`

```python
def check_order(
    self,
    portfolio: Any,
    order: Any,
    current_prices: dict[str, Decimal],
) -> tuple[bool, RiskAction, str]:
    """Pre-trade risk check.

    Returns:
        (allowed, action, reason)
    """
```

### Example 4: Order Validation

```python
from rustybt.finance.execution import MarketOrder
from rustybt.assets import Equity

# Create order
order = MarketOrder(asset=Equity("AAPL"), amount=Decimal("1000"))

# Check order
current_prices = {"AAPL": Decimal("150.00")}
allowed, action, reason = risk_mgr.check_order(
    portfolio=portfolio,
    order=order,
    current_prices=current_prices,
)

if allowed:
    if action == RiskAction.WARN:
        logger.warning("risk_warning", reason=reason)
    # Execute order
    execute_order(order)
else:
    logger.error("order_rejected", reason=reason)
```

### Leverage Check

**Source**: `risk.py:315-362`

```python
def _check_leverage_limit(...) -> tuple[bool, RiskAction, str]:
    """Check leverage limit.

    Formula:
        leverage = (total_exposure + order_exposure) / total_equity
    """
```

### Concentration Check

**Source**: `risk.py:364-420`

```python
def _check_concentration_limit(...) -> tuple[bool, RiskAction, str]:
    """Check concentration limit.

    Formula:
        concentration = asset_exposure / total_equity
    """
```

### Drawdown Check

**Source**: `risk.py:422-482`

```python
def _check_drawdown_limit(...) -> tuple[bool, RiskAction, str]:
    """Check drawdown limit.

    Formula:
        drawdown = (current_value - peak_value) / peak_value
    """
```

### Example 5: Leverage Violation

```python
# Portfolio: $1M equity, $1.8M exposure (1.8x leverage)
# Limit: 2.0x max

order = MarketOrder(asset=Equity("AAPL"), amount=Decimal("2000"))
# Would add $300k exposure → 2.1x leverage

allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

print(allowed)  # False
print(action)   # RiskAction.REJECT
print(reason)   # "Leverage limit exceeded: 2.10x > 2.00x"
```

### Example 6: Drawdown Halt

```python
# Peak: $1,000,000
# Current: $780,000
# Drawdown: -22% (exceeds 20% halt threshold)

allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

print(action)  # RiskAction.HALT
print(risk_mgr.limits.trading_halted)  # True

# All subsequent orders rejected until manual reset
```

---

## Real-Time Risk Metrics

### RiskMetrics

**Source**: `risk.py:103-166`

```python
@dataclass
class RiskMetrics:
    """Real-time risk metrics."""
    timestamp: pd.Timestamp

    # Leverage
    total_exposure: Decimal
    total_equity: Decimal
    leverage: Decimal

    # Concentration
    max_asset_exposure: Decimal
    max_asset_symbol: str | None

    # Drawdown
    current_value: Decimal
    peak_value: Decimal
    current_drawdown: Decimal
    max_drawdown: Decimal

    # Volatility & VaR
    portfolio_volatility: Decimal
    var_95: Decimal
    var_99: Decimal

    # Optional
    portfolio_beta: Decimal | None = None
    avg_strategy_correlation: Decimal | None = None
```

### calculate_metrics()

**Source**: `risk.py:502-590`

```python
def calculate_metrics(
    self,
    portfolio: Any,
    current_prices: dict[str, Decimal],
    market_returns: list[Decimal] | None = None,
) -> RiskMetrics:
    """Calculate real-time risk metrics."""
```

### Example 7: Monitor Risk Metrics

```python
# In backtest loop
for timestamp, data in data_feed:
    portfolio.execute_bar(timestamp, data)

    # Get current prices
    current_prices = {asset: data[asset]["price"] for asset in data}

    # Calculate metrics
    metrics = risk_mgr.calculate_metrics(
        portfolio=portfolio,
        current_prices=current_prices,
    )

    # Log metrics
    print(f"\n=== Risk Metrics ({timestamp.date()}) ===")
    print(f"Leverage: {float(metrics.leverage):.2f}x")
    print(f"Max Asset: {float(metrics.max_asset_exposure):.1%} ({metrics.max_asset_symbol})")
    print(f"Drawdown: {float(metrics.current_drawdown):.2%}")
    print(f"Volatility: {float(metrics.portfolio_volatility):.1%}")
    print(f"VaR 95%: ${float(metrics.var_95):,.2f}")

    # Check violations
    if metrics.leverage > risk_mgr.limits.warn_portfolio_leverage:
        logger.warning("leverage_warning", leverage=f"{float(metrics.leverage):.2f}x")
```

---

## Value at Risk (VaR)

### calculate_var()

**Source**: `risk.py:671-738`

```python
def calculate_var(
    self,
    portfolio: Any,
    confidence_level: Decimal,
    portfolio_value: Decimal
) -> Decimal:
    """Calculate VaR using Historical Simulation.

    Formula:
        VaR_α = -percentile(returns, 1-α) × portfolio_value

    Example:
        95% confidence: 5th percentile return = -2.5%
        VaR_95 = -(-2.5%) × $1,000,000 = $25,000

        Interpretation: 95% confident daily loss won't exceed $25k
    """
```

### Example 8: VaR Calculation

```python
portfolio_value = Decimal("1000000")

# Calculate VaR at 95% and 99%
var_95 = risk_mgr.calculate_var(
    portfolio=portfolio,
    confidence_level=Decimal("0.95"),
    portfolio_value=portfolio_value,
)

var_99 = risk_mgr.calculate_var(
    portfolio=portfolio,
    confidence_level=Decimal("0.99"),
    portfolio_value=portfolio_value,
)

print(f"VaR 95%: ${float(var_95):,.2f}")  # $25,000
print(f"VaR 99%: ${float(var_99):,.2f}")  # $45,000

# Check against limit
if var_95 / portfolio_value > risk_mgr.limits.max_var_pct:
    logger.error("var_limit_exceeded")
```

---

## Volatility Targeting

### apply_volatility_targeting()

**Source**: `risk.py:925-988`

```python
def apply_volatility_targeting(
    self,
    portfolio: Any,
    current_allocations: dict[str, Decimal]
) -> dict[str, Decimal]:
    """Adjust allocations to maintain target volatility.

    Formula:
        scaling_factor = target_vol / current_vol
        new_allocation_i = current_allocation_i × scaling_factor
    """
```

### Example 9: Volatility Targeting

```python
# Current vol: 18%, Target: 12%
current_allocs = {
    "momentum": Decimal("0.40"),
    "mean_rev": Decimal("0.35"),
    "trend": Decimal("0.25"),
}

# Reduce allocations to hit target
adjusted_allocs = risk_mgr.apply_volatility_targeting(
    portfolio=portfolio,
    current_allocations=current_allocs,
)

# Scaling factor: 12% / 18% = 0.667
print(adjusted_allocs)
# {
#     'momentum': Decimal('0.267'),    # 40% × 0.667
#     'mean_rev': Decimal('0.233'),    # 35% × 0.667
#     'trend': Decimal('0.167')         # 25% × 0.667
# }

# Apply rebalancing
portfolio.rebalance(adjusted_allocs, reason="Volatility targeting")
```

---

## Production Examples

### Example 10: Complete Risk Management Integration

```python
from decimal import Decimal
from rustybt.portfolio.allocator import PortfolioAllocator
from rustybt.portfolio.risk import RiskManager, RiskLimits

# 1. Setup
limits = RiskLimits(
    max_portfolio_leverage=Decimal("2.0"),
    max_single_asset_exposure=Decimal("0.15"),
    max_drawdown=Decimal("0.15"),
    target_volatility=Decimal("0.12"),
)

risk_mgr = RiskManager(limits=limits, lookback_window=252)
portfolio = PortfolioAllocator(total_capital=Decimal("1000000"))

portfolio.add_strategy("momentum", MomentumStrategy(), Decimal("0.50"))
portfolio.add_strategy("mean_rev", MeanReversionStrategy(), Decimal("0.50"))

# 2. Backtest with risk management
for timestamp, data in data_feed:
    current_prices = {asset: data[asset]["price"] for asset in data}

    # Execute strategies
    portfolio.execute_bar(timestamp, data)

    # Calculate risk metrics
    metrics = risk_mgr.calculate_metrics(portfolio, current_prices)

    # Check violations
    if metrics.leverage > limits.warn_portfolio_leverage:
        logger.warning("leverage_warning", leverage=f"{float(metrics.leverage):.2f}x")

    if metrics.current_drawdown < -abs(limits.warn_drawdown):
        logger.warning("drawdown_warning", dd=f"{float(metrics.current_drawdown):.2%}")

    # Monthly: volatility targeting
    if timestamp.day == 1:
        if metrics.portfolio_volatility > limits.target_volatility:
            current_allocs = {
                sid: alloc.allocated_capital / portfolio.total_capital
                for sid, alloc in portfolio.strategies.items()
            }
            adjusted = risk_mgr.apply_volatility_targeting(portfolio, current_allocs)
            portfolio.rebalance(adjusted, reason="Volatility targeting")

# 3. Final report
final_metrics = risk_mgr.calculate_metrics(portfolio, current_prices)
print("\n=== Final Risk Report ===")
print(final_metrics.to_dict())
```

### Example 11: Pre-Trade Risk Integration

```python
def submit_order_with_risk_check(portfolio, order, risk_mgr, current_prices):
    """Submit order with pre-trade risk check."""
    allowed, action, reason = risk_mgr.check_order(
        portfolio=portfolio,
        order=order,
        current_prices=current_prices,
    )

    if not allowed:
        if action == RiskAction.HALT:
            logger.error("trading_halted", reason=reason)
            return None
        elif action == RiskAction.REJECT:
            logger.error("order_rejected", reason=reason)
            return None

    if action == RiskAction.WARN:
        logger.warning("risk_warning", reason=reason)

    # Execute order
    return portfolio.execute_order(order)
```

---

## Best Practices

### 1. Limit Configuration

**DO**:
- Start conservative (1.5x leverage, 10% concentration)
- Set warn/max/halt thresholds
- Match limits to fund mandate

**DON'T**:
- Skip warn thresholds
- Set limits too loose (> 6x leverage)

### 2. Pre-Trade Checks

**DO**:
- Check ALL orders before execution
- Log rejections with reasons
- Monitor warnings

```python
allowed, action, reason = risk_mgr.check_order(portfolio, order, current_prices)

if not allowed:
    logger.error("order_rejected", reason=reason)
    return

if action == RiskAction.WARN:
    logger.warning("risk_warning", reason=reason)
```

**DON'T**:
- Execute without checking
- Override REJECT/HALT

### 3. Real-Time Monitoring

**DO**:
- Calculate metrics daily
- Log to database
- Set up alerts

```python
metrics = risk_mgr.calculate_metrics(portfolio, current_prices)
store_to_db(timestamp, metrics.to_dict())

if metrics.leverage > limits.warn_portfolio_leverage:
    send_alert(f"Leverage warning: {float(metrics.leverage):.2f}x")
```

**DON'T**:
- Calculate only at end
- Ignore warnings

### 4. Drawdown Management

**DO**:
- Set clear halt thresholds (15-25%)
- Liquidate when halted
- Require manual review

```python
if risk_mgr.limits.trading_halted:
    logger.error("trading_halted")
    # Pause all strategies
    for sid in portfolio.strategies:
        portfolio.pause_strategy(sid)
```

**DON'T**:
- Continue trading during halt
- Auto-resume after halt

### 5. VaR Monitoring

**DO**:
- Calculate at 95% and 99%
- Check against historical losses
- Use as one of many metrics

```python
var_95 = risk_mgr.calculate_var(portfolio, Decimal("0.95"), portfolio_value)
var_99 = risk_mgr.calculate_var(portfolio, Decimal("0.99"), portfolio_value)

if var_95 / portfolio_value > limits.max_var_pct:
    logger.error("var_limit_exceeded")
```

**DON'T**:
- Rely solely on VaR
- Ignore fat tails

### 6. Volatility Targeting

**DO**:
- Set realistic targets (10-15%)
- Rebalance monthly
- Account for transaction costs

```python
# Monthly check
if timestamp.day == 1:
    current_vol = metrics.portfolio_volatility
    if abs(current_vol - target_vol) / target_vol > Decimal("0.20"):
        adjusted = risk_mgr.apply_volatility_targeting(portfolio, current_allocs)
        portfolio.rebalance(adjusted, reason="Volatility targeting")
```

**DON'T**:
- Rebalance daily
- Set unrealistic targets (< 5% or > 30%)

---

## Cross-References

- **Portfolio Allocation**: `allocation-multistrategy.md`
- **Order Aggregation**: `order-aggregation.md`
- **Performance Metrics**: `../analytics/performance-metrics.md`

---

## Summary

RustyBT's risk management provides **institutional-grade** controls:

✅ **Pre-Trade Checks**: Leverage, concentration, drawdown
✅ **Real-Time Monitoring**: Daily metrics and alerts
✅ **Comprehensive Metrics**: VaR, beta, correlation, volatility
✅ **Limit Enforcement**: Warn, reduce, reject, halt
✅ **Volatility Targeting**: Dynamic allocation adjustment
✅ **Production-Ready**: Logging, audit trail, alerts

**Key Takeaway**: Use `RiskManager` with appropriate `RiskLimits` for all production portfolios. Always perform pre-trade checks, calculate metrics daily, and respond to violations immediately.
