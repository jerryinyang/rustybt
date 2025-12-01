# Strategy Implementation Guide

This guide explains how to add new strategies to the rustybt validation framework.

## Overview: Why Dual Implementation?

The validation framework compares rustybt against Backtrader to verify correctness. This requires:

1. **Identical Logic**: Both implementations must execute the same trading logic
2. **Structured Logging**: Both produce JSONL logs with identical schemas
3. **Layer Comparison**: Logs are compared across 5 validation layers

```
Your Strategy Logic
        │
    ┌───┴───┐
    ▼       ▼
┌───────┐ ┌───────────┐
│rustybt│ │Backtrader │
└───┬───┘ └─────┬─────┘
    ▼           ▼
 rustybt.jsonl  backtrader.jsonl
    │           │
    └─────┬─────┘
          ▼
    Comparison Engine
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
  Layer1 Layer2 ...
```

## Log Schema

All log events follow this JSON schema:

```json
{
    "timestamp": "2025-01-15T10:30:00.123",
    "layer": "data|signals|orders|broker|portfolio",
    "event": "descriptive_event_name",
    "asset": "AAPL",
    "data": {
        "key": "value"
    }
}
```

**Layers:**
- `data` - Price data, bar events, initialization
- `signals` - Indicator values, computed signals
- `orders` - Order creation events
- `broker` - Fill execution, rejections
- `portfolio` - Position changes, P&L updates

## Base Classes

### rustybt: `RustyBTValidatedStrategy`

Located in `rustybt/validation/base_strategy.py`:

```python
from pathlib import Path
from rustybt.validation.base_strategy import RustyBTValidatedStrategy

class MyStrategy(RustyBTValidatedStrategy):
    def __init__(self, log_path: Path, **params):
        super().__init__(log_path)
        # Store your parameters
        self.fast_period = params.get('fast_period', 10)
        self.slow_period = params.get('slow_period', 30)

    def initialize(self, context):
        super().initialize(context)  # Logs "initialize" event
        # Custom initialization
        self._log_event(
            layer="data",
            event="strategy_init",
            data={"fast_period": self.fast_period}
        )

    def handle_data(self, context, data):
        super().handle_data(context, data)  # Logs "bar_received"
        # Your trading logic here
```

**Key Methods:**
- `_log_event(layer, event, data, asset=None)` - Core logging
- `log_signal(signal_name, signal_value, asset=None, **extra)` - Signal convenience
- `log_order_created(order_type, asset, quantity, **extra)` - Order convenience
- `log_broker_event(event, asset=None, **extra)` - Broker convenience

### Backtrader: `BacktraderValidatedStrategy`

Located in `tests/validation/strategies/bt_strategies/base_validated.py`:

```python
import backtrader as bt
from tests.validation.strategies.bt_strategies.base_validated import (
    BacktraderValidatedStrategy
)

class MyStrategy(BacktraderValidatedStrategy):
    params = (
        ('log_path', None),
        ('fast_period', 10),
        ('slow_period', 30),
    )

    def __init__(self):
        super().__init__()
        # Create indicators using Backtrader's built-in
        self.fast_sma = bt.indicators.SMA(
            self.data.close,
            period=self.p.fast_period
        )
        # Log initialization
        self._log_event(
            layer="data",
            event="strategy_init",
            data={"fast_period": self.p.fast_period}
        )

    def next(self):
        super().next()  # Logs "bar_received"
        # Your trading logic here
```

## Step-by-Step Walkthrough: Bollinger Bands Strategy

Let's implement a Bollinger Bands mean reversion strategy in both frameworks.

### Step 1: Define Strategy Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| period | int | 20 | Bollinger Band period |
| std_dev | float | 2.0 | Standard deviation multiplier |
| target_percent | float | 1.0 | Position size (100%) |

### Step 2: rustybt Implementation

Create `tests/validation/strategies/rustybt/bollinger_bands.py`:

```python
"""Bollinger Bands strategy for rustybt validation.

This implementation uses rustybt's real APIs:
- data.history() for price data access
- order_target_percent() for trade execution
- context.portfolio for position/cash tracking
"""

from __future__ import annotations
from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy
from rustybt.api import order_target_percent


class BollingerBandsStrategy(RustyBTValidatedStrategy):
    """Bollinger Bands mean reversion strategy using real rustybt APIs."""

    def __init__(
        self,
        log_path: Path,
        period: int = 20,
        std_dev: float = 2.0,
        target_percent: float = 1.0,
    ) -> None:
        super().__init__(log_path)
        self._period = period
        self._std_dev = std_dev
        self._target_percent = target_percent

        # Band values (calculated from data.history())
        self._sma: float | None = None
        self._upper_band: float | None = None
        self._lower_band: float | None = None

        # Position tracking
        self._position_state: int = 0  # 0 = flat, 1 = long

        # Asset reference (set during initialize)
        self._asset: Any = None
        self._asset_str: str | None = None

        # Bar counter for warmup
        self._bar_count: int = 0

    def initialize(self, context: Any) -> None:
        super().initialize(context)

        # Get asset from context (set by execute_rustybt.py)
        if hasattr(context, "asset"):
            self._asset = context.asset
            self._asset_str = str(context.asset) if context.asset else None

        self._log_event(
            layer="data",
            event="bb_init",
            data={
                "period": self._period,
                "std_dev": self._std_dev,
                "target_percent": self._target_percent,
            },
        )

    def _calculate_bands_from_history(self, data: Any) -> tuple[float, float, float] | None:
        """Calculate Bollinger Bands using rustybt's data.history() API."""
        if self._asset is None:
            return None

        try:
            # Use rustybt's data.history() API
            prices = data.history(self._asset, "close", self._period, "1d")

            if prices is None or len(prices) < self._period:
                return None

            # Calculate SMA and standard deviation using pandas
            sma = float(prices.mean())
            std = float(prices.std())

            upper_band = sma + self._std_dev * std
            lower_band = sma - self._std_dev * std

            return (sma, upper_band, lower_band)
        except Exception:
            return None

    def handle_data(self, context: Any, data: Any) -> Any:
        self._bar_count += 1

        # Skip warmup period
        if self._bar_count <= self._period:
            return None

        super().handle_data(context, data)

        # Get current price using rustybt's data.current()
        try:
            price = float(data.current(self._asset, "price"))
        except Exception:
            return None

        # Calculate bands using rustybt's data.history()
        bands = self._calculate_bands_from_history(data)
        if bands is None:
            return None

        self._sma, self._upper_band, self._lower_band = bands

        # Log indicator values (Layer 2)
        self._log_event(
            layer="signals",
            event="indicator_values",
            data={
                "sma": self._sma,
                "upper_band": self._upper_band,
                "lower_band": self._lower_band,
                "price": price,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Compute signal
        if price < self._lower_band:
            signal = "BUY"  # Oversold
        elif price > self._upper_band:
            signal = "SELL"  # Overbought
        else:
            signal = "HOLD"

        # Log signal (Layer 2)
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "sma": self._sma,
                "upper_band": self._upper_band,
                "lower_band": self._lower_band,
                "signal": signal,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute using rustybt's order API
        order_result = None

        if signal == "BUY" and self._position_state == 0:
            self.log_order_created(
                order_type="market",
                asset=self._asset_str or "UNKNOWN",
                quantity=self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
            )
            order_result = order_target_percent(self._asset, self._target_percent)
            self._position_state = 1

            # Log transaction (Layer 4)
            self.log_transaction(
                asset=self._asset_str or "UNKNOWN",
                quantity=100,  # Simplified
                price=price,
                commission=1.0,
            )

        elif signal == "SELL" and self._position_state == 1:
            self.log_order_created(
                order_type="market",
                asset=self._asset_str or "UNKNOWN",
                quantity=-self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
            )
            order_result = order_target_percent(self._asset, 0.0)
            self._position_state = 0

            # Log transaction (Layer 4)
            self.log_transaction(
                asset=self._asset_str or "UNKNOWN",
                quantity=-100,  # Simplified
                price=price,
                commission=1.0,
            )

        return order_result
```

**Key points for rustybt strategies:**
- Use `data.history(asset, field, period, frequency)` for indicator data
- Use `order_target_percent()` for trade execution
- Access portfolio via `context.portfolio.portfolio_value`, `context.portfolio.cash`
- Never use manual deque-based calculations or homebrew broker simulation

### Step 3: Backtrader Implementation

Create `tests/validation/strategies/bt_strategies/bollinger_bands.py`:

```python
"""Bollinger Bands strategy for Backtrader validation."""

from __future__ import annotations
import backtrader as bt

from tests.validation.strategies.bt_strategies.base_validated import (
    BacktraderValidatedStrategy,
)


class BollingerBandsStrategy(BacktraderValidatedStrategy):
    """Bollinger Bands mean reversion strategy."""

    params = (
        ("log_path", None),
        ("period", 20),
        ("std_dev", 2.0),
        ("target_percent", 1.0),
    )

    def __init__(self) -> None:
        super().__init__()

        # Use Backtrader's built-in Bollinger Bands indicator
        self.bb = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.period,
            devfactor=self.p.std_dev,
        )

        # Position state tracking
        self._position_state: int = 0

        # Log initialization
        self._log_event(
            layer="data",
            event="bb_init",
            data={
                "period": self.p.period,
                "std_dev": self.p.std_dev,
                "target_percent": self.p.target_percent,
            },
        )

    def next(self) -> None:
        super().next()

        # Get current values
        price = self.data.close[0]
        sma = self.bb.mid[0]
        upper = self.bb.top[0]
        lower = self.bb.bot[0]

        asset = self.data._name if hasattr(self.data, "_name") else None

        # Log indicator values (must match rustybt structure exactly)
        self._log_event(
            layer="signals",
            event="indicator_values",
            data={
                "sma": sma,
                "upper_band": upper,
                "lower_band": lower,
                "price": price,
            },
            asset=asset,
        )

        # Compute signal (same logic as rustybt)
        if price < lower:
            signal = "BUY"
        elif price > upper:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Log signal
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "sma": sma,
                "upper_band": upper,
                "lower_band": lower,
                "signal": signal,
            },
            asset=asset,
        )

        # Execute orders
        if signal == "BUY" and self._position_state == 0:
            self.order_target_percent(target=self.p.target_percent)
            self._position_state = 1
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self.p.target_percent,
            )

        elif signal == "SELL" and self._position_state == 1:
            self.order_target_percent(target=0.0)
            self._position_state = 0
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self.p.target_percent,
            )
```

### Step 4: Register Strategy

Add to `tests/validation/strategies/rustybt/__init__.py`:
```python
from .bollinger_bands import BollingerBandsStrategy
```

Add to `tests/validation/strategies/bt_strategies/__init__.py`:
```python
from .bollinger_bands import BollingerBandsStrategy
```

## Strategy Audit Checklist

Before submitting a new strategy, verify:

### Logic Equivalence

| Check | Status |
|-------|--------|
| Same indicator calculation formula | ☐ |
| Same signal generation conditions | ☐ |
| Same order execution logic | ☐ |
| Same position tracking | ☐ |
| Same parameter defaults | ☐ |

### Log Schema Parity

| Check | Status |
|-------|--------|
| Same event names | ☐ |
| Same layer assignments | ☐ |
| Same data field names | ☐ |
| Same data types (floats, strings) | ☐ |
| Same null handling | ☐ |

### Testing Verification

| Check | Status |
|-------|--------|
| Both strategies compile | ☐ |
| Both produce valid JSONL | ☐ |
| Log comparison shows 0 discrepancies | ☐ |
| Edge cases handled identically | ☐ |

## Common Pitfalls

### 1. Indicator Calculation Differences

**Problem:** Backtrader uses 0-indexed lookback, rustybt may differ.

**Solution:** Explicitly log indicator values at each step to verify:
```python
# Log the actual values being used
self._log_event(
    layer="signals",
    event="indicator_values",
    data={"fast_sma": self.fast_sma[0], "slow_sma": self.slow_sma[0]},
)
```

### 2. Timing Differences

**Problem:** Order execution timing varies between frameworks.

**Solution:** Use layer-appropriate logging:
- `orders` layer: Log when order is *created*
- `broker` layer: Log when order is *filled*

### 3. Numeric Precision

**Problem:** Floating-point comparison fails due to precision.

**Solution:** Use tolerance in comparisons:
```yaml
# tolerances.yaml
signals:
  indicator_values:
    fast_sma: 1e-6
    slow_sma: 1e-6
```

### 4. Asset Name Inconsistency

**Problem:** rustybt uses symbol(), Backtrader uses data._name.

**Solution:** Normalize asset extraction:
```python
# rustybt
asset = str(context.asset) if hasattr(context, "asset") else None

# Backtrader
asset = self.data._name if hasattr(self.data, "_name") else None
```

### 5. Position State Tracking

**Problem:** Backtrader has built-in position, rustybt doesn't.

**Solution:** Track position manually in both:
```python
self._position_state: int = 0  # 0 = flat, 1 = long
```

## Running Validation

### Single Strategy Validation

```bash
# Create session
rustybt-validate session create \
    --strategy bollinger_bands \
    --data tests/validation/fixtures/validation_data.parquet

# Run validation
rustybt-validate run <session_id>

# Check results
rustybt-validate report <session_id>
```

### Adding to Test Suite

Create `tests/validation/test_bollinger_bands.py`:

```python
"""Validation tests for Bollinger Bands strategy."""
import pytest
from pathlib import Path

from tests.validation.strategies.rustybt.bollinger_bands import (
    BollingerBandsStrategy as RustyBTStrategy
)
from tests.validation.strategies.bt_strategies.bollinger_bands import (
    BollingerBandsStrategy as BTStrategy
)


class TestBollingerBandsValidation:
    """Tests for Bollinger Bands strategy validation."""

    def test_parameters_match(self):
        """Verify both strategies have identical parameters."""
        assert RustyBTStrategy.__init__.__defaults__ == (20, 2.0, 1.0)
        assert BTStrategy.params[1:] == (
            ("period", 20),
            ("std_dev", 2.0),
            ("target_percent", 1.0),
        )

    def test_log_schema_match(self, tmp_path):
        """Verify log schemas are identical."""
        # Test implementation here
        pass
```

## Next Steps

- **[Investigation Workflow Guide](investigation-guide.md)** - Investigate any discrepancies
- **[Design Differences](design-differences.md)** - Known intentional differences
- **[Getting Started](getting-started.md)** - Run your first validation session
