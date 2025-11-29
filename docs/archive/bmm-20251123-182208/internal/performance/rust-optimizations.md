# Rust Optimizations in RustyBT

**Version**: 1.0
**Last Updated**: 2025-01-09
**Status**: Production Ready

## Overview

RustyBT includes optional Rust-accelerated implementations of performance-critical operations. These optimizations are transparent to users—if Rust extensions are unavailable, the system automatically falls back to pure Python implementations.

## Optimized Operations

The following operations have Rust-optimized implementations:

### Technical Indicators

| Function | Description | Typical Speedup |
|----------|-------------|-----------------|
| `rust_sma` | Simple Moving Average | 1.4-1.7x |
| `rust_ema` | Exponential Moving Average | 1.4-1.6x |
| `rust_rolling_sum` | Rolling window sum | 1.1-1.2x |

### Array Operations

| Function | Description | Typical Speedup |
|----------|-------------|-----------------|
| `rust_array_sum` | Array summation | 1.0-1.5x |
| `rust_mean` | Array mean | 1.0-1.5x |
| `rust_window_slice` | Extract data window | 20-28x |
| `rust_index_select` | Select by indices | 10-28x |
| `rust_fillna` | Fill NaN values | 1.8-2.4x |
| `rust_pairwise_op` | Element-wise operations | 0.3-0.5x* |

*Note: Pairwise operations show overhead due to Python↔Rust conversion. Use for large batches.

## When to Use Rust Optimizations

### ✅ Good Use Cases (Rust Provides Real Speedups)

**Use Rust optimizations when:**

1. **Large Datasets** (10,000+ elements)
   - Conversion overhead is amortized over large computations
   - SMA/EMA on 10,000+ bars: 1.4-1.7× speedup

2. **Complex Multi-Pass Algorithms**
   - Rolling windows, moving averages, exponential smoothing
   - Computation cost >> conversion cost

3. **Custom Indicators on Historical Data**
   - Backtesting scenarios with years of data
   - Strategy optimization over large parameter spaces

### ❌ When NOT to Use Rust (Python/Polars Faster)

**Avoid Rust optimizations when:**

1. **Small Datasets** (< 1,000 elements)
   - Conversion overhead dominates computation time
   - Example: SMA on 100 bars shows minimal speedup (1.06×)

2. **Simple Operations** (sum, mean, basic math)
   - Python builtins are C-optimized and faster when you factor in conversion
   - `rust_array_sum` is **12-25× SLOWER** than `sum()` due to Vec allocation

3. **DataFrame Operations**
   - **Polars is already Rust-backed** - adding another layer just adds overhead
   - Use native Polars operations (group_by, filter, agg) instead
   - Example: DataPortal uses pure Polars (fastest option)

4. **Operations Polars/NumPy Already Optimize**
   - Array slicing, indexing, filtering: let Polars/NumPy handle it
   - They're already optimized and avoid conversion overhead

### Performance Principle

**The Golden Rule**: Only use Rust when **computation cost >> conversion cost**

**Conversion cost includes**:
- Allocating `Vec<f64>` and copying Python list → Rust
- Converting back from Rust → Python list
- For large datasets with complex operations, this is negligible
- For small/simple operations, this dominates runtime

### Real-World Example: DataPortal

The profiling identified `DataPortal.history()` as a bottleneck (61.5% of runtime), but we **intentionally don't use custom Rust** there because:

1. **Polars is already Rust-optimized** for DataFrame operations
2. **Benchmarks confirmed**: `rust_index_select` is **25× slower** than pure Polars
3. **Better solution**: Let Polars do what it does best

Our Rust optimizations are **available for custom strategies** where they provide real value on large datasets.

## Decimal Precision Support

**Critical Feature**: All Rust optimizations fully support Python's `Decimal` type for financial-grade precision.

### How It Works

1. **Detection**: The wrapper automatically detects `Decimal` values in input data
2. **Context**: Python's Decimal context (precision, rounding mode) is passed to Rust
3. **Conversion**: Values are safely converted maintaining full precision
4. **Results**: Rust returns `Decimal` objects matching Python's behavior exactly

### Example

```python
from decimal import Decimal, getcontext
from rustybt.rust_optimizations import rust_sma

# Configure precision
getcontext().prec = 28
getcontext().rounding = 'ROUND_HALF_UP'

# Works seamlessly with Decimal
prices = [Decimal("100.123456"), Decimal("101.234567"), Decimal("102.345678")]
sma = rust_sma(prices, window=2)

# Result preserves Decimal precision
assert all(isinstance(v, Decimal) for v in sma if not v.is_nan())
```

### Supported Decimal Operations

All functions that accept numeric inputs support Decimal:
- `rust_sma`, `rust_ema`, `rust_rolling_sum`
- `rust_array_sum`, `rust_mean`
- `rust_window_slice`, `rust_index_select`
- `rust_fillna`, `rust_pairwise_op`

## Fallback Behavior

When Rust extensions are not installed or fail to load:

```python
from rustybt import rust_optimizations

# Check if Rust is available
if rust_optimizations.RUST_AVAILABLE:
    print("Using Rust optimizations")
else:
    print("Using Python fallbacks")

# API remains identical regardless
result = rust_optimizations.rust_sma(data, window=20)
```

### Logging

The module logs optimization status:

```
INFO: Rust optimizations available and loaded
```

Or:

```
WARNING: Rust optimizations not available (ModuleNotFoundError: No module named '_rustybt'), using Python fallbacks
```

## Integration Points

### DataPortal (Uses Pure Polars)

The `PolarsDataPortal` uses **pure Polars** for DataFrame operations (Polars is already Rust-optimized):

```python
from rustybt.data.polars import PolarsDataPortal

portal = PolarsDataPortal(daily_reader=reader)

# Uses native Polars operations (already Rust-backed and optimal)
history = portal.get_history_window(
    assets=[asset],
    end_dt=pd.Timestamp("2023-01-10"),
    bar_count=30,
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# DataPortal does NOT use our custom Rust because:
# 1. Polars is already Rust-optimized for these operations
# 2. Adding another Rust layer would add overhead (25× slower in benchmarks)
# 3. Better to let Polars do what it does best
```

### Custom Strategies

You can directly use Rust optimizations in your trading strategies:

```python
from rustybt import TradingAlgorithm
from rustybt.rust_optimizations import rust_sma, rust_ema

class MACrossStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')

    def handle_data(self, context, data):
        # Get price history as Decimal
        prices = data.history(context.asset, 'close', 50, '1d')

        # Compute indicators with Rust acceleration
        sma_20 = rust_sma(prices, window=20)
        sma_50 = rust_sma(prices, window=50)

        # Trading logic
        if sma_20[-1] > sma_50[-1]:
            self.order_target_percent(context.asset, 1.0)
        else:
            self.order_target_percent(context.asset, 0.0)
```

## Configuration

### Precision Settings

Rust respects Python's Decimal context:

```python
from decimal import getcontext

# Set precision (default: 28)
getcontext().prec = 18

# Set rounding mode
getcontext().rounding = 'ROUND_HALF_UP'

# All Rust operations will use these settings
```

### Supported Rounding Modes

| Python Mode | Rust Equivalent | Description |
|-------------|-----------------|-------------|
| `ROUND_HALF_UP` | `MidpointAwayFromZero` | Round .5 away from zero |
| `ROUND_HALF_EVEN` | `MidpointNearestEven` | Banker's rounding |
| `ROUND_DOWN` | `ToZero` | Truncate toward zero |
| `ROUND_UP` | `AwayFromZero` | Round away from zero |
| `ROUND_CEILING` | `ToPositiveInfinity` | Round toward +∞ |
| `ROUND_FLOOR` | `ToNegativeInfinity` | Round toward -∞ |

## Performance Gains

Based on benchmarks with 10,000-element arrays:

**Float Operations**:
- SMA: 1.47x faster
- EMA: 1.5x faster
- Array sum: 1.05x faster
- Mean: 1.06x faster

**Decimal Operations**:
- SMA (Decimal): ~3x slower than float (expected due to precision)
- Decimal operations maintain precision while being faster than naive Python loops

**Data Operations**:
- Window slice: 20x faster
- Index select: 28x faster
- Fill NaN: 1.8x faster

See `docs/performance/rust-benchmarks.md` for detailed benchmark results.

## Testing

### Equivalence Tests

Property-based tests ensure Rust and Python produce identical results:

```bash
pytest tests/rust/test_rust_equivalence.py
```

Over 500 test cases per function verify:
- Numerical equivalence (float operations)
- Decimal precision preservation
- Edge cases (empty arrays, NaN values, etc.)
- Rounding mode correctness

### Integration Tests

End-to-end tests verify Rust-optimized backtests produce identical results:

```bash
pytest tests/integration/test_rust_backtest.py
```

## Installation

Rust optimizations are built automatically when installing from source:

```bash
# Install with Rust support (requires Rust toolchain)
cd rust/crates/rustybt
maturin develop --release

# Or install pre-built wheels (when available)
pip install rustybt  # Includes Rust extensions
```

### Requirements

- Rust 1.90+ (for building from source)
- Python 3.12+
- `maturin` build tool

### Verifying Installation

```python
from rustybt import rust_optimizations

assert rust_optimizations.RUST_AVAILABLE, "Rust extensions not loaded"
print("✓ Rust optimizations available")
```

## Troubleshooting

### Rust Extensions Not Loading

**Problem**: `RUST_AVAILABLE = False`

**Solutions**:
1. Check installation: `pip list | grep rustybt`
2. Rebuild extensions: `cd rust/crates/rustybt && maturin develop --release`
3. Check logs for import errors

### Decimal Precision Mismatch

**Problem**: Results differ from pure Python Decimal

**Checks**:
1. Verify precision setting: `getcontext().prec`
2. Check rounding mode: `getcontext().rounding`
3. Run equivalence tests: `pytest tests/rust/test_rust_equivalence.py -k decimal`

### Performance Not Improving

**Problem**: No speedup observed

**Possible Causes**:
1. Small dataset (overhead dominates)
2. Fallback to Python (check `RUST_AVAILABLE`)
3. Conversion overhead (for very small operations)

**Solution**: Use Rust optimizations for datasets with 100+ elements.

## Future Enhancements

Planned optimizations (see Epic 7 roadmap):

1. **Additional Indicators**: RSI, Bollinger Bands, MACD
2. **Metrics Calculations**: Sharpe ratio, drawdown, returns
3. **Batch Operations**: Process multiple assets simultaneously
4. **SIMD**: Leverage CPU vector instructions
5. **Parallel Processing**: Multi-threaded indicator calculations

## Technical Details

### Architecture

```
Python Layer (rustybt/rust_optimizations.py)
    ↓
  Detection (_has_decimal)
    ↓
  ┌─────────┬──────────┐
  │  Float  │ Decimal  │
  └────┬────┴─────┬────┘
       ↓          ↓
   Rust Float  Rust Decimal (rust-decimal)
       ↓          ↓
   PyO3 Bridge
       ↓
   Return to Python
```

### PyO3 Bindings

Functions are exposed via PyO3 with `#[pyfunction]` attributes:

```rust
#[pyfunction]
pub fn rust_decimal_sma(
    values: &Bound<'_, PyList>,
    window: usize,
    scale: u32,
    rounding: &str,
) -> PyResult<Vec<Py<PyAny>>> {
    // Implementation
}
```

### Zero-Copy Where Possible

For float operations, data passes with minimal copying. For Decimal, conversion is necessary but optimized.

## References

- [Rust Decimal Crate](https://docs.rs/rust_decimal/)
- [PyO3 Documentation](https://pyo3.rs/)
- [Story 7.3: Implement Rust-Optimized Modules](../stories/7.3.implement-rust-optimized-modules.story.md)
- [Benchmark Results](./rust-benchmarks.md)

---

**Note**: This document describes the production implementation of Rust optimizations in RustyBT v0.1.0+.
