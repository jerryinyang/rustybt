# Capital Allocation Algorithms

**Source**: `rustybt/portfolio/allocation.py`
**Verified**: 2025-10-16

## Overview

Capital allocation algorithms determine how to distribute portfolio capital across multiple trading strategies. RustyBT provides 5 allocation algorithms ranging from simple fixed weights to sophisticated growth-optimal allocation.

**Why Allocation Matters**: Proper capital allocation maximizes risk-adjusted returns while managing portfolio-level risk. Different strategies have different risk/return profiles - smart allocation compounds gains and limits losses.

## Allocation Algorithm Hierarchy

```
AllocationAlgorithm (Abstract Base)           # allocation.py:29
├── FixedAllocation                          # allocation.py:154
├── DynamicAllocation                         # allocation.py:212
├── RiskParityAllocation                      # allocation.py:302
├── KellyCriterionAllocation                  # allocation.py:407
└── DrawdownBasedAllocation                   # allocation.py:545

AllocationConstraints                         # allocation.py:131
AllocationRebalancer                          # allocation.py:645
```

---

## Abstract Base Class

### AllocationAlgorithm

**Source**: `rustybt/portfolio/allocation.py:29`

Base class for all capital allocation algorithms.

**Key Requirements**:
1. Implement `calculate_allocations()` method
2. Return allocations as `Dict[strategy_id, allocation_pct]`
3. Ensure allocations sum to ≤ 1.0 (100%)
4. Handle edge cases (zero volatility, insufficient data)
5. Use Decimal precision for all calculations

**Key Methods**:

```python
@abstractmethod
def calculate_allocations(
    self, strategies: dict[str, StrategyPerformance]
) -> dict[str, Decimal]:
    """Calculate allocation percentages for each strategy.

    Args:
        strategies: Dict mapping strategy_id to StrategyPerformance

    Returns:
        Dict mapping strategy_id to allocation_pct (0.0 to 1.0)
        Sum of allocations must be <= 1.0
    """
```

**Helper Methods** (source line 63-127):

```python
def apply_constraints(
    self, allocations: dict[str, Decimal]
) -> dict[str, Decimal]:
    """Apply min/max constraints and normalize.

    - Applies per-strategy min/max limits
    - Logs when constraints applied
    - Normalizes to sum to 1.0
    """

def normalize_allocations(
    self, allocations: dict[str, Decimal]
) -> dict[str, Decimal]:
    """Normalize allocations to sum to 1.0.

    If total is zero, falls back to equal allocation.
    """
```

---

### AllocationConstraints

**Source**: `rustybt/portfolio/allocation.py:131`

Constraints for capital allocation to enforce min/max limits.

**Attributes** (source line 140-143):
```python
@dataclass
class AllocationConstraints:
    default_min: Decimal = Decimal("0.0")      # Global minimum (0%)
    default_max: Decimal = Decimal("1.0")      # Global maximum (100%)
    strategy_min: dict[str, Decimal] = {}      # Per-strategy minimums
    strategy_max: dict[str, Decimal] = {}      # Per-strategy maximums
```

**Methods**:
```python
def get_min(self, strategy_id: str) -> Decimal:
    """Get minimum allocation for strategy (uses default if not specified)."""

def get_max(self, strategy_id: str) -> Decimal:
    """Get maximum allocation for strategy (uses default if not specified)."""
```

**Example**:
```python
from rustybt.portfolio.allocation import AllocationConstraints
from decimal import Decimal as D

# Set global and per-strategy constraints
constraints = AllocationConstraints(
    default_min=D("0.05"),    # All strategies: minimum 5%
    default_max=D("0.40"),    # All strategies: maximum 40%
    strategy_min={
        "strategy_1": D("0.10")  # Strategy 1: minimum 10%
    },
    strategy_max={
        "strategy_2": D("0.30")  # Strategy 2: maximum 30%
    }
)
```

---

## Allocation Algorithms

### FixedAllocation

**Source**: `rustybt/portfolio/allocation.py:154`

Static percentage allocation - never changes.

**Formula**: Pre-defined weights (does not adjust to performance)

**Use Case**: Conservative allocation when you have predefined strategy weights.

**Example**:
```python
from rustybt.portfolio.allocation import FixedAllocation, AllocationConstraints
from decimal import Decimal as D

# Define fixed allocations
fixed_alloc = FixedAllocation(
    allocations={
        "momentum_strategy": D("0.40"),    # 40%
        "mean_reversion": D("0.30"),       # 30%
        "trend_following": D("0.30")       # 30%
    },
    constraints=None  # Optional
)

# Calculate allocations (always returns same weights)
allocations = fixed_alloc.calculate_allocations(strategies)
# Returns: {'momentum_strategy': 0.40, 'mean_reversion': 0.30, 'trend_following': 0.30}
```

**Behavior** (source line 195-209):
- Returns same allocations every time
- Only returns allocations for active strategies
- Ignores performance data completely
- Applies constraints if provided

**When to Use**:
- ✅ Backtesting with fixed weights
- ✅ Conservative allocation (no adaptation)
- ✅ Regulatory requirements for fixed allocations
- ✅ Strategies with known long-term performance

**Advantages**:
- ✅ Simple and predictable
- ✅ No overfitting to recent performance
- ✅ Easy to understand and explain

**Limitations**:
- ❌ Doesn't adapt to changing market conditions
- ❌ Can over-allocate to poorly performing strategies
- ❌ Misses opportunities to capitalize on winners

---

### DynamicAllocation

**Source**: `rustybt/portfolio/allocation.py:212`

Performance-based allocation - momentum approach.

**Formula** (source line 215-217):
```
score_i = (return_i - min_return) / (max_return - min_return)
allocation_i = (score_i + min_allocation) / Σ(score_j + min_allocation)
```

**Winners get more capital, losers get less.**

**Parameters** (source line 224-235):
- `lookback_window` (int, default=60): Number of periods for performance calculation
- `min_allocation` (Decimal, default=0.05): Minimum allocation for any strategy (5%)
- `constraints` (AllocationConstraints, optional): Optional constraints

**Example**:
```python
from rustybt.portfolio.allocation import DynamicAllocation
from decimal import Decimal as D

# Momentum-based allocation
dynamic_alloc = DynamicAllocation(
    lookback_window=60,             # 60 days (~3 months)
    min_allocation=D("0.05"),       # 5% minimum per strategy
    constraints=None
)

# Strategies with recent performance:
# strategy_1: +10% return over 60 days
# strategy_2: +5% return over 60 days
# strategy_3: -2% return over 60 days

allocations = dynamic_alloc.calculate_allocations(strategies)
# Returns (example):
# {
#     'strategy_1': 0.50,  # Best performer gets most capital
#     'strategy_2': 0.35,  # Medium performer gets medium capital
#     'strategy_3': 0.15   # Poor performer gets minimum
# }
```

**Detailed Calculation** (source line 247-299):

```python
# Step 1: Calculate returns for each strategy over lookback window
strategy_1_returns = [0.001, 0.002, ...] # 60 days of returns
cumulative_return_1 = sum(strategy_1_returns) = 0.10 (10%)

strategy_2_returns = [0.0005, 0.001, ...] # 60 days of returns
cumulative_return_2 = sum(strategy_2_returns) = 0.05 (5%)

strategy_3_returns = [-0.0001, -0.0002, ...] # 60 days of returns
cumulative_return_3 = sum(strategy_3_returns) = -0.02 (-2%)

# Step 2: Normalize to 0-1 range
min_return = -0.02
max_return = 0.10
range = 0.10 - (-0.02) = 0.12

score_1 = (0.10 - (-0.02)) / 0.12 = 1.00  # Best
score_2 = (0.05 - (-0.02)) / 0.12 = 0.58  # Medium
score_3 = (-0.02 - (-0.02)) / 0.12 = 0.00 # Worst

# Step 3: Add minimum allocation (prevents zero allocation)
adjusted_score_1 = 1.00 + 0.05 = 1.05
adjusted_score_2 = 0.58 + 0.05 = 0.63
adjusted_score_3 = 0.00 + 0.05 = 0.05

# Step 4: Normalize to sum to 1.0
total = 1.05 + 0.63 + 0.05 = 1.73

allocation_1 = 1.05 / 1.73 = 0.607 (60.7%)
allocation_2 = 0.63 / 1.73 = 0.364 (36.4%)
allocation_3 = 0.05 / 1.73 = 0.029 (2.9%)
```

**Edge Cases** (source line 275-284):
- **All returns equal**: Falls back to equal weighting
- **Insufficient data**: Uses zero return for that strategy
- **No strategies**: Returns empty dict

**When to Use**:
- Momentum-based strategies
- Markets with persistent trends
- Strategies with variable performance
- Want to capitalize on recent winners

**Advantages**:
- ✅ Adapts to performance
- ✅ Momentum effect (winners keep winning)
- ✅ Automatically reduces exposure to losers
- ✅ Minimum allocation prevents abandoning strategies

**Limitations**:
- ❌ Can chase past performance (may not predict future)
- ❌ Slower to adapt to regime changes
- ❌ Lookback window selection critical

**Parameter Tuning**:
- **Short window (20-40 days)**: Fast adaptation, more noise
- **Medium window (60-120 days)**: Balanced, recommended default
- **Long window (200+ days)**: Slow adaptation, more stable

---

### RiskParityAllocation

**Source**: `rustybt/portfolio/allocation.py:302`

Volatility-weighted allocation for equal risk contribution.

**Formula** (source line 305-306):
```
w_i = (1/σ_i) / Σ(1/σ_j)
```

Where `σ_i` is the annualized volatility (standard deviation of returns) of strategy i.

**Goal**: Each strategy contributes equal volatility to the portfolio.

**Parameters** (source line 315-327):
- `lookback_window` (int, default=252): Number of periods for volatility calculation (1 year daily)
- `min_volatility` (Decimal, default=0.001): Minimum volatility to avoid division by zero
- `constraints` (AllocationConstraints, optional): Optional constraints

**Example**:
```python
from rustybt.portfolio.allocation import RiskParityAllocation
from decimal import Decimal as D

# Risk parity allocation
risk_parity = RiskParityAllocation(
    lookback_window=252,              # 1 year daily data
    min_volatility=D("0.001"),        # 0.1% minimum
    constraints=None
)

# Strategies with different volatilities:
# high_vol_strategy: 30% annual volatility
# medium_vol_strategy: 15% annual volatility
# low_vol_strategy: 5% annual volatility

allocations = risk_parity.calculate_allocations(strategies)
# Returns (example):
# {
#     'high_vol_strategy': 0.15,    # Low allocation (high vol)
#     'medium_vol_strategy': 0.30,  # Medium allocation (medium vol)
#     'low_vol_strategy': 0.55      # High allocation (low vol)
# }
```

**Detailed Calculation** (source line 338-404):

```python
# Step 1: Calculate volatility for each strategy
strategy_returns_1 = [0.02, -0.01, 0.03, ...]  # 252 days
std_1 = np.std(strategy_returns_1, ddof=1) = 0.0194
vol_1 = 0.0194 × sqrt(252) = 0.30 (30% annual)

strategy_returns_2 = [0.01, -0.005, 0.01, ...]  # 252 days
std_2 = np.std(strategy_returns_2, ddof=1) = 0.0097
vol_2 = 0.0097 × sqrt(252) = 0.15 (15% annual)

strategy_returns_3 = [0.003, -0.002, 0.004, ...]  # 252 days
std_3 = np.std(strategy_returns_3, ddof=1) = 0.0032
vol_3 = 0.0032 × sqrt(252) = 0.05 (5% annual)

# Step 2: Calculate inverse volatility weights
inverse_vol_1 = 1 / 0.30 = 3.33
inverse_vol_2 = 1 / 0.15 = 6.67
inverse_vol_3 = 1 / 0.05 = 20.00

# Step 3: Normalize to sum to 1.0
total_inverse = 3.33 + 6.67 + 20.00 = 30.00

allocation_1 = 3.33 / 30.00 = 0.111 (11.1%)
allocation_2 = 6.67 / 30.00 = 0.222 (22.2%)
allocation_3 = 20.00 / 30.00 = 0.667 (66.7%)

# Result: Low-volatility strategy gets highest allocation
# This equalizes risk contribution across strategies
```

**Risk Contribution Verification**:
```python
# After allocation, each strategy contributes equal portfolio volatility
strategy_1_contribution = 0.111 × 0.30 = 0.0333 (3.33%)
strategy_2_contribution = 0.222 × 0.15 = 0.0333 (3.33%)
strategy_3_contribution = 0.667 × 0.05 = 0.0335 (3.35%)
# All approximately equal!
```

**Volatility Calculation** (source line 338-368):
```python
def calculate_volatility(self, returns: list[Decimal]) -> Decimal:
    """
    Calculate annualized volatility from returns.

    Formula:
        σ_annual = std(returns) × sqrt(252)

    Uses sample standard deviation (ddof=1)
    Annualizes assuming 252 trading days
    """
```

**When to Use**:
- ✅ Diversified portfolio construction
- ✅ Strategies with varying risk profiles
- ✅ Want balanced risk exposure
- ✅ Institutional risk management

**Advantages**:
- ✅ Balances risk across strategies
- ✅ Naturally reduces allocation to volatile strategies
- ✅ Well-established academic approach
- ✅ Works well with uncorrelated strategies

**Limitations**:
- ❌ Requires sufficient return history (252+ observations)
- ❌ Past volatility may not predict future volatility
- ❌ Ignores correlation between strategies
- ❌ Can over-allocate to low-vol strategies

**Best Practices**:
- Use with strategies that have similar Sharpe ratios
- Consider correlation matrix for advanced risk parity
- Monitor rolling volatility for regime changes
- Combine with maximum allocation constraints

---

### KellyCriterionAllocation

**Source**: `rustybt/portfolio/allocation.py:407`

Growth-optimal allocation using Kelly criterion.

**Formula** (source line 410-411):
```
f*_i = (μ_i / σ²_i) × kelly_fraction
```

Where:
- `μ_i` = expected return (mean return)
- `σ²_i` = variance of returns
- `kelly_fraction` = fraction of full Kelly to use (typically 0.25-0.50)

**Goal**: Maximize long-term geometric growth rate.

**Parameters** (source line 422-437):
- `lookback_window` (int, default=252): Number of periods for return/variance calculation
- `kelly_fraction` (Decimal, default=0.5): Fraction of Kelly to use (0.5 = half-Kelly, conservative)
- `min_variance` (Decimal, default=0.0001): Minimum variance to avoid division by zero
- `constraints` (AllocationConstraints, optional): Optional constraints

**Example**:
```python
from rustybt.portfolio.allocation import KellyCriterionAllocation
from decimal import Decimal as D

# Kelly criterion allocation (half-Kelly for safety)
kelly_alloc = KellyCriterionAllocation(
    lookback_window=252,              # 1 year
    kelly_fraction=D("0.5"),          # Half-Kelly (conservative)
    min_variance=D("0.0001"),
    constraints=None
)

# Strategies with different return/risk profiles:
# aggressive: 20% return, 30% volatility → Sharpe 0.67
# moderate: 12% return, 15% volatility → Sharpe 0.80
# conservative: 6% return, 5% volatility → Sharpe 1.20

allocations = kelly_alloc.calculate_allocations(strategies)
# Returns (example - favors high Sharpe ratios):
# {
#     'aggressive': 0.25,        # High return but high variance
#     'moderate': 0.35,          # Balanced
#     'conservative': 0.40       # High Sharpe gets most allocation
# }
```

**Detailed Calculation** (source line 449-540):

```python
# Strategy 1: Aggressive
returns_1 = [0.002, -0.001, 0.003, ...]  # 252 daily returns
mean_return_1 = mean(returns_1) = 0.0008 (daily)
annualized_mean_1 = 0.0008 × 252 = 0.20 (20%)
variance_1 = var(returns_1) = 0.00037
annualized_variance_1 = 0.00037 × 252 = 0.09324

kelly_fraction_1 = 0.20 / 0.09324 = 2.14
fractional_kelly_1 = 2.14 × 0.5 = 1.07

# Strategy 2: Moderate
mean_return_2 = 0.00047 (daily)
annualized_mean_2 = 0.00047 × 252 = 0.12 (12%)
variance_2 = 0.000092
annualized_variance_2 = 0.000092 × 252 = 0.02318

kelly_fraction_2 = 0.12 / 0.02318 = 5.18
fractional_kelly_2 = 5.18 × 0.5 = 2.59

# Strategy 3: Conservative
mean_return_3 = 0.00024 (daily)
annualized_mean_3 = 0.00024 × 252 = 0.06 (6%)
variance_3 = 0.000010
annualized_variance_3 = 0.000010 × 252 = 0.00252

kelly_fraction_3 = 0.06 / 0.00252 = 23.81
fractional_kelly_3 = 23.81 × 0.5 = 11.90

# Normalize to sum to 1.0
total = 1.07 + 2.59 + 11.90 = 15.56

allocation_1 = 1.07 / 15.56 = 0.069 (6.9%)
allocation_2 = 2.59 / 15.56 = 0.166 (16.6%)
allocation_3 = 11.90 / 15.56 = 0.765 (76.5%)

# Conservative strategy (high Sharpe) gets most allocation
```

**Kelly Fraction Recommendations** (source line 425):
- **Full Kelly (1.0)**: Maximum growth, very aggressive, high drawdowns
- **Half Kelly (0.5)**: Recommended default, reduces drawdowns by ~50%
- **Quarter Kelly (0.25)**: Conservative, smooth equity curve
- **One-tenth Kelly (0.1)**: Very conservative, minimal risk

**When to Use**:
- Growth-focused portfolios
- Strategies with positive expected returns
- Long-term compounding goals
- Can tolerate volatility

**Advantages**:
- ✅ Mathematically optimal for long-term growth
- ✅ Favors high Sharpe ratio strategies
- ✅ Automatically sizes based on risk/return
- ✅ Well-studied in literature

**Limitations**:
- ❌ Full Kelly can be extremely aggressive
- ❌ Assumes returns are stationary (not always true)
- ❌ Sensitive to mean return estimation errors
- ❌ Can recommend overleveraged positions

**Risk Management**:
```python
# Always use fractional Kelly
kelly_alloc = KellyCriterionAllocation(
    kelly_fraction=D("0.25")  # Quarter-Kelly for safety
)

# Add maximum allocation constraints
constraints = AllocationConstraints(
    default_max=D("0.50")  # No strategy > 50%
)

kelly_alloc = KellyCriterionAllocation(
    kelly_fraction=D("0.5"),
    constraints=constraints
)
```

---

### DrawdownBasedAllocation

**Source**: `rustybt/portfolio/allocation.py:545`

Drawdown-aware allocation - reduces allocation during drawdowns.

**Formula** (adaptive based on current drawdown):
```
If drawdown < threshold:
    allocation_i = base_allocation_i

If drawdown >= threshold:
    allocation_i = base_allocation_i × reduction_factor
```

**Parameters**:
- `base_allocator` (AllocationAlgorithm): Underlying allocation algorithm
- `drawdown_threshold` (Decimal, default=0.10): Drawdown % that triggers reduction (10%)
- `reduction_factor` (Decimal, default=0.50): Allocation multiplier during drawdown (50%)
- `lookback_window` (int, default=252): Drawdown calculation window

**Example**:
```python
from rustybt.portfolio.allocation import (
    DrawdownBasedAllocation,
    RiskParityAllocation
)
from decimal import Decimal as D

# Base allocation (risk parity)
base_alloc = RiskParityAllocation(lookback_window=252)

# Wrap with drawdown protection
drawdown_alloc = DrawdownBasedAllocation(
    base_allocator=base_alloc,
    drawdown_threshold=D("0.10"),     # Trigger at 10% drawdown
    reduction_factor=D("0.50"),       # Reduce allocation by 50%
    lookback_window=252
)

# Normal conditions (no drawdown):
# strategy_1: 40% allocation (from base_alloc)
# strategy_2: 35% allocation
# strategy_3: 25% allocation

# During 15% drawdown (exceeds 10% threshold):
# strategy_1: 40% × 0.50 = 20% allocation
# strategy_2: 35% × 0.50 = 17.5% allocation
# strategy_3: 25% × 0.50 = 12.5% allocation
# Remaining 50% allocated to cash
```

**When to Use**:
- ✅ Risk management overlay
- ✅ Drawdown-sensitive portfolios
- ✅ Want to reduce risk during losses
- ✅ Behavioral risk management

**Advantages**:
- ✅ Protects capital during drawdowns
- ✅ Flexible (wraps any base allocator)
- ✅ Simple drawdown-based trigger
- ✅ Reduces emotional decision-making

**Limitations**:
- ❌ May exit too early in temporary drawdowns
- ❌ Misses recovery if allocation reduced
- ❌ Drawdown threshold selection critical

---

## Complete Example

```python
from rustybt.portfolio.allocation import (
    AllocationAlgorithm,
    AllocationConstraints,
    FixedAllocation,
    DynamicAllocation,
    RiskParityAllocation,
    KellyCriterionAllocation,
    DrawdownBasedAllocation
)
from decimal import Decimal as D

# Example 1: Fixed Allocation
fixed = FixedAllocation(
    allocations={
        "strategy_1": D("0.50"),
        "strategy_2": D("0.30"),
        "strategy_3": D("0.20")
    }
)

# Example 2: Dynamic with Constraints
constraints = AllocationConstraints(
    default_min=D("0.05"),  # All strategies: min 5%
    default_max=D("0.50"),  # All strategies: max 50%
)

dynamic = DynamicAllocation(
    lookback_window=60,
    min_allocation=D("0.05"),
    constraints=constraints
)

# Example 3: Risk Parity
risk_parity = RiskParityAllocation(
    lookback_window=252,
    min_volatility=D("0.001")
)

# Example 4: Half-Kelly with Constraints
kelly = KellyCriterionAllocation(
    lookback_window=252,
    kelly_fraction=D("0.5"),  # Half-Kelly
    constraints=constraints
)

# Example 5: Risk Parity with Drawdown Protection
base = RiskParityAllocation(lookback_window=252)
protected = DrawdownBasedAllocation(
    base_allocator=base,
    drawdown_threshold=D("0.10"),
    reduction_factor=D("0.50")
)

# Calculate allocations (given strategies dict)
allocations = protected.calculate_allocations(strategies)
```

---

## Comparison Table

| Algorithm | Adapts to Performance | Adapts to Volatility | Complexity | Use Case |
|-----------|----------------------|---------------------|------------|----------|
| FixedAllocation | ❌ No | ❌ No | ⭐ Simple | Backtesting, conservative |
| DynamicAllocation | ✅ Yes (momentum) | ❌ No | ⭐⭐ Moderate | Trend-following |
| RiskParityAllocation | ❌ No | ✅ Yes (inverse vol) | ⭐⭐⭐ Moderate | Balanced risk |
| KellyCriterionAllocation | ✅ Yes (Sharpe) | ✅ Yes (variance) | ⭐⭐⭐⭐ Complex | Growth optimal |
| DrawdownBasedAllocation | ✅ Yes (via base) | ✅ Yes (via base) | ⭐⭐⭐⭐ Complex | Risk overlay |

**Recommendation**:
- **Conservative**: `RiskParityAllocation` with constraints
- **Moderate**: `DynamicAllocation` with 60-day window
- **Aggressive**: `KellyCriterionAllocation` with half-Kelly
- **Risk-Aware**: `DrawdownBasedAllocation` wrapping any base allocator

---

## Related Documentation

- [Portfolio Allocator](portfolio-allocator.md) - Multi-strategy management system
- [Risk Management](risk-management.md) - Position limits and exposure controls
- [Performance Metrics](performance/metrics.md) - Strategy performance tracking

## Verification

✅ All algorithms verified in source code
✅ All formulas match implementation
✅ All parameters documented
✅ No fabricated APIs

**Verification Date**: 2025-10-16
**Source File**: `rustybt/portfolio/allocation.py:29,131,154,212,302,407,545,645`
