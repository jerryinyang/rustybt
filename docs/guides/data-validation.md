# Data Validation Guide

RustyBT provides comprehensive multi-layer data validation to ensure data quality and prevent errors caused by invalid OHLCV data.

## Overview

The validation system consists of 4 layers:

1. **Layer 1: Schema Validation** - Validates data types, required fields, and value ranges using Pydantic
2. **Layer 2: OHLCV Relationship Validation** - Ensures OHLCV relationships are valid (e.g., high ≥ low)
3. **Layer 3: Outlier Detection** - Identifies price spikes and volume anomalies
4. **Layer 4: Temporal Consistency** - Validates timestamps are sorted, no duplicates, no future data, and detects gaps

## Quick Start

### Basic Usage

```python
from decimal import Decimal
from datetime import datetime
import polars as pl
from rustybt.data.polars.validation import DataValidator, ValidationConfig

# Create sample OHLCV data
data = pl.DataFrame({
    "timestamp": [datetime(2023, 1, i) for i in range(1, 11)],
    "open": [Decimal("100")] * 10,
    "high": [Decimal("105")] * 10,
    "low": [Decimal("95")] * 10,
    "close": [Decimal("102")] * 10,
    "volume": [Decimal("1000")] * 10,
})

# Create validator with default config
validator = DataValidator()

# Validate data
result = validator.validate(data)

if result.valid:
    print(f"✓ Data validation passed ({result.row_count} rows)")
else:
    print(f"✗ Validation failed with {len(result.get_errors())} errors:")
    for error in result.get_errors():
        print(f"  - Layer {error.layer}: {error.message}")
```

### Validation with Specific Layers

```python
# Only validate schema and OHLCV relationships (skip outliers and temporal)
result = validator.validate(data, layers=[1, 2])

# Only validate outliers
result = validator.validate(data, layers=[3])
```

### Raise on Validation Errors

```python
from rustybt.exceptions import DataValidationError

try:
    validator.validate_and_raise(data)
    print("Data is valid!")
except DataValidationError as e:
    print(f"Validation failed: {e}")
```

## Configuration

### Default Configuration

```python
config = ValidationConfig(
    # Layer 1: Schema validation
    enforce_schema=True,

    # Layer 2: OHLCV relationships
    enforce_ohlcv_relationships=True,

    # Layer 3: Outlier detection
    enable_outlier_detection=True,
    price_spike_threshold_std=5.0,  # Standard deviations
    volume_spike_threshold=10.0,    # Multiple of mean volume

    # Layer 4: Temporal consistency
    enforce_temporal_consistency=True,
    allow_gaps=True,
    max_gap_days=7,
    expected_frequency="1d",
)

validator = DataValidator(config)
```

### Crypto-Specific Configuration

For 24/7 cryptocurrency markets:

```python
config = ValidationConfig.for_crypto()
validator = DataValidator(config)

# Crypto config has:
# - Higher price spike threshold (8.0 std devs) - crypto is more volatile
# - Higher volume spike threshold (20x mean)
# - No gaps allowed (24/7 markets)
# - Max gap: 1 day
```

### Stock-Specific Configuration

For traditional stock markets:

```python
config = ValidationConfig.for_stocks()
validator = DataValidator(config)

# Stock config has:
# - Lower price spike threshold (5.0 std devs)
# - Standard volume spike threshold (10x mean)
# - Gaps allowed (weekends/holidays)
# - Max gap: 7 days
```

### Custom Configuration

```python
config = ValidationConfig(
    enable_outlier_detection=True,
    price_spike_threshold_std=3.0,  # More sensitive to price spikes
    volume_spike_threshold=5.0,      # More sensitive to volume spikes
    allow_gaps=False,                # Strict - no gaps allowed
    expected_frequency="1h",         # Hourly data
)
```

## Validation Layers

### Layer 1: Schema Validation

Validates:
- ✓ Required columns exist (`timestamp`, `open`, `high`, `low`, `close`, `volume`)
- ✓ No NULL values in required columns
- ✓ All prices are positive (> 0)
- ✓ Volume is non-negative (≥ 0)

**Example violations:**
- Missing `open` column
- NULL values in `timestamp`
- Negative prices
- Negative volume

### Layer 2: OHLCV Relationship Validation

Validates:
- ✓ `high` ≥ `low` (all bars)
- ✓ `high` ≥ `open` (all bars)
- ✓ `high` ≥ `close` (all bars)
- ✓ `low` ≤ `open` (all bars)
- ✓ `low` ≤ `close` (all bars)

**Example violations:**
- Bar with `high` = 90, `low` = 95 (high < low)
- Bar with `high` = 100, `open` = 105 (high < open)

### Layer 3: Outlier Detection

Detects:
- ⚠️ Price spikes (return exceeds N standard deviations from mean)
- ⚠️ Volume spikes (volume exceeds M × mean volume)

**Note:** Outliers generate WARNING-level violations (not errors) since they may be legitimate.

**Configuration:**
```python
config = ValidationConfig(
    price_spike_threshold_std=5.0,   # Flag if |return - mean| > 5σ
    volume_spike_threshold=10.0,      # Flag if volume > 10 × mean
)
```

### Layer 4: Temporal Consistency

Validates:
- ✓ Timestamps are sorted in ascending order
- ✓ No duplicate timestamps
- ✓ No future data (timestamp > current time)
- ⚠️ No excessive gaps in data (configurable)

**Gap detection:**
```python
config = ValidationConfig(
    allow_gaps=True,           # WARNING if gaps found
    max_gap_days=7,            # Maximum allowed gap
    expected_frequency="1d",   # Expected data frequency
)

# For stricter validation (ERROR on gaps):
config = ValidationConfig(allow_gaps=False)
```

## Integration with Data Adapters

### Validate on Data Ingestion

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter
from rustybt.data.polars.validation import DataValidator, ValidationConfig

# Create data adapter with validator
config = ValidationConfig.for_stocks()
validator = DataValidator(config)

adapter = YFinanceAdapter(
    name="yfinance",
    validator=validator,  # Validates data before returning
)

# Fetch data (automatically validated)
data = await adapter.fetch(
    symbols=["AAPL", "MSFT"],
    start_date=pd.Timestamp("2023-01-01"),
    end_date=pd.Timestamp("2023-12-31"),
    resolution="1d",
)
# If validation fails, raises DataValidationError
```

### Validate in DataPortal

```python
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.polars.validation import DataValidator, ValidationConfig

# Create data portal with validator
config = ValidationConfig(
    enforce_schema=True,
    enforce_ohlcv_relationships=True,
    enable_outlier_detection=False,  # Skip expensive outlier detection
    enforce_temporal_consistency=True,
)
validator = DataValidator(config)

portal = PolarsDataPortal(
    data_source=data_source,
    validator=validator,  # Lightweight validation on data access
)
```

## Error Severity

Validation violations have two severity levels:

### ERROR (Critical)

Prevents data usage. Raised for:
- Missing required columns
- NULL values
- Negative prices/volume
- Invalid OHLCV relationships (high < low, etc.)
- Unsorted timestamps
- Duplicate timestamps
- Future data

### WARNING (Suspicious)

Data is usable but suspicious. Flagged for:
- Price outliers (extreme returns)
- Volume spikes
- Data gaps (if `allow_gaps=True`)

**Checking severity:**
```python
result = validator.validate(data)

if result.has_errors():
    print(f"Critical errors: {len(result.get_errors())}")
    for error in result.get_errors():
        print(f"  {error.message}")

if result.has_warnings():
    print(f"Warnings: {len(result.get_warnings())}")
    for warning in result.get_warnings():
        print(f"  {warning.message}")
```

## Interpreting Validation Errors

### Example: Missing Columns

```
ERROR: Missing required columns: ['open', 'high']
```

**Fix:** Ensure your DataFrame has all required OHLCV columns.

### Example: OHLCV Relationship Violation

```
ERROR: High < Low in 5 rows
Details: {invalid_row_count: 5, sample_rows: [...]}
```

**Fix:** Check data source for errors. High price must be ≥ low price.

### Example: Price Outlier

```
WARNING: Price outliers detected in 2 rows
Details: {outlier_count: 2, threshold_std: 5.0, sample_rows: [...]}
```

**Action:** Investigate if extreme price movements are legitimate or data errors.

### Example: Future Data

```
ERROR: Future data detected: 10 rows with timestamps > now
Details: {future_row_count: 10, current_time: '2025-01-01 12:00:00'}
```

**Fix:** Check data source timestamps. May indicate timezone issues.

## Best Practices

### 1. Validate at Ingestion

Always validate data when ingesting from external sources:

```python
adapter = YFinanceAdapter(validator=DataValidator(ValidationConfig.for_stocks()))
```

### 2. Lightweight Validation in Strategy

Use lighter validation during strategy execution to avoid performance overhead:

```python
config = ValidationConfig(
    enforce_schema=True,
    enforce_ohlcv_relationships=True,
    enable_outlier_detection=False,  # Skip expensive outlier detection
)
portal = PolarsDataPortal(data_source=source, validator=DataValidator(config))
```

### 3. Asset-Class Specific Configuration

Use appropriate config for your asset class:

```python
# For stocks
validator = DataValidator(ValidationConfig.for_stocks())

# For crypto
validator = DataValidator(ValidationConfig.for_crypto())
```

### 4. Handle Warnings Appropriately

Warnings don't prevent trading but should be logged:

```python
result = validator.validate(data)
if result.has_warnings():
    for warning in result.get_warnings():
        logger.warning(f"Data quality warning: {warning.message}")
```

## API Reference

### DataValidator

```python
class DataValidator:
    def __init__(self, config: ValidationConfig | None = None)
    def validate(self, df: pl.DataFrame, layers: list[int] | str = "all") -> ValidationResult
    def validate_and_raise(self, df: pl.DataFrame, layers: list[int] | str = "all") -> None
```

### ValidationConfig

```python
@dataclass
class ValidationConfig:
    enforce_schema: bool = True
    enforce_ohlcv_relationships: bool = True
    enable_outlier_detection: bool = True
    price_spike_threshold_std: float = 5.0
    volume_spike_threshold: float = 10.0
    enforce_temporal_consistency: bool = True
    allow_gaps: bool = True
    max_gap_days: int = 7
    expected_frequency: str = "1d"

    @classmethod
    def for_crypto(cls) -> ValidationConfig

    @classmethod
    def for_stocks(cls) -> ValidationConfig
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    valid: bool
    violations: list[ValidationViolation]
    row_count: int
    metadata: dict[str, Any]

    def has_errors(self) -> bool
    def has_warnings(self) -> bool
    def get_errors(self) -> list[ValidationViolation]
    def get_warnings(self) -> list[ValidationViolation]
```

### ValidationViolation

```python
@dataclass
class ValidationViolation:
    layer: int  # 1-4
    severity: ValidationSeverity  # ERROR or WARNING
    message: str
    details: dict[str, Any]
```

## Troubleshooting

### High False Positive Rate for Outliers

If outlier detection flags too many legitimate price movements:

```python
config = ValidationConfig(
    price_spike_threshold_std=8.0,  # Increase threshold (less sensitive)
    volume_spike_threshold=20.0,
)
```

### Performance Issues

If validation is too slow during strategy execution:

```python
# Disable outlier detection (most expensive layer)
config = ValidationConfig(enable_outlier_detection=False)

# Or only validate critical layers
result = validator.validate(data, layers=[1, 2])  # Schema + OHLCV only
```

### Timezone Issues with Future Data Detection

Ensure timestamps are timezone-aware:

```python
from datetime import timezone
data = pl.DataFrame({
    "timestamp": [datetime.now(timezone.utc)],
    ...
})
```

## See Also

- [Exception Handling Guide](./exception-handling.md)
- [Audit Logging Guide](./audit-logging.md)
- [DataSource API Reference](../api/datasource-api.md)
