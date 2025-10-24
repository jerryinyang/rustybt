# Strategy Code Capture

## Overview

RustyBT automatically captures your strategy source code during backtest execution, ensuring complete reproducibility. **As of Story 001, RustyBT uses intelligent entry point detection to capture only the necessary files** (typically just your strategy file), reducing storage by 90%+ for optimization runs.

## Why Code Capture?

### Reproducibility

Strategies evolve over time. Code capture ensures you can:
- Reproduce exact backtest results weeks or months later
- Compare strategy versions side-by-side
- Audit what code produced specific results
- Track strategy evolution over time

### Compliance & Auditing

For regulated environments or institutional use:
- Complete audit trail of strategy versions
- Verification of deployed vs backtested code
- Historical record for compliance reviews

### Team Collaboration

When working with teams:
- Share exact code that produced results
- Review historical strategy versions
- Onboard new team members with historical context

## Capture Methods

RustyBT supports two code capture methods with automatic intelligent selection:

### 1. Entry Point Detection (Automatic) - **NEW DEFAULT**

**Default method** - Uses runtime introspection (`inspect.stack()`) to detect the file containing the `run_algorithm()` call.

**Pros:**
- **90%+ storage reduction** vs old import analysis (1 file vs 10+ files)
- Zero configuration required
- Perfect for optimization runs (100 backtests = 100 files, not 1000+)
- Automatically handles edge cases (Jupyter notebooks, interactive sessions)

**Behavior:**
- ✅ Standard Python file → Detects and captures entry point file only
- ✅ Jupyter notebook → Detects .ipynb file
- ✅ No detection possible (frozen app, interactive) → Gracefully skips capture
- ✅ `strategy.yaml` exists → Always uses YAML (explicit wins)

**Cons:**
- Only captures the entry point file (not imports)
- For multi-file strategies, use `strategy.yaml`

### 2. Strategy YAML (Explicit)

**Manual method** - Explicitly specify files to capture.

**Pros:**
- Capture any file type (JSON, CSV, YAML, etc.)
- Full control over captured files
- Works with dynamic imports
- **Always takes precedence** over entry point detection

**Cons:**
- Requires manual configuration
- Need to update when adding files

---

!!! tip "Which Method to Use?"
    - **Single-file strategies**: No action needed - entry point detection handles it automatically
    - **Multi-file strategies**: Create `strategy.yaml` to explicitly list all required files
    - **Optimization runs**: Entry point detection saves 90%+ storage (recommended!)

## Entry Point Detection (NEW)

### How It Works

The system uses Python's `inspect.stack()` to detect the file that called `run_algorithm()`:

```python
# my_strategy.py
from rustybt import run_algorithm

def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    # Strategy logic
    pass

# This is the entry point - detected automatically!
run_algorithm(
    start='2020-01-01',
    end='2020-12-31',
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000
)
```

**Captured files (NEW):**
- `my_strategy.py` **ONLY** (1 file instead of 10+!)

**Storage savings:**
- Old behavior: ~50KB per backtest (10+ files)
- New behavior: ~5KB per backtest (1 file)
- **90% storage reduction!**

**Why this is better for optimization:**
- 100-run optimization: 100 files (5MB) instead of 1000+ files (50MB)
- Faster I/O, less disk space, cleaner output directories

### Edge Case Handling

Entry point detection automatically handles special execution environments:

**✅ Standard Python file:**
```python
# my_strategy.py
run_algorithm(...)  # Detected and captured automatically
```

**✅ Jupyter Notebook:**
```python
# Cell in strategy.ipynb
run_algorithm(...)  # Detects .ipynb file, captures notebook
```

**⚠️ Interactive Python shell:**
```python
>>> run_algorithm(...)  # Cannot detect source file, skips capture gracefully
```

**⚠️ Frozen application (PyInstaller, cx_Freeze):**
```python
# Compiled executable
run_algorithm(...)  # Cannot access source, skips capture gracefully
```

**Note:** When detection fails, code capture is gracefully skipped (never fails your backtest). Use `strategy.yaml` if you need capture in these scenarios.

### Example: Single-File Strategy (NEW DEFAULT)

```
my_project/
└── momentum_strategy.py       # Entry point - ONLY file captured!
```

**momentum_strategy.py:**
```python
from indicators.technical import calculate_rsi  # NOT captured
from indicators.custom import custom_momentum    # NOT captured
from risk.position_sizing import calculate_position_size  # NOT captured
from config import params  # NOT captured

def initialize(context):
    context.rsi_threshold = params.RSI_THRESHOLD

def handle_data(context, data):
    rsi = calculate_rsi(data)
    momentum = custom_momentum(data)

    if rsi < context.rsi_threshold:
        size = calculate_position_size(context, data)
        order(context.asset, size)

# Entry point - THIS file gets captured
run_algorithm(
    start='2020-01-01',
    end='2020-12-31',
    initialize=initialize,
    handle_data=handle_data
)
```

**Captured structure (NEW):**
```
backtests/20251019_143527_123/code/
└── momentum_strategy.py        # ONLY the entry point!
```

**Storage:** 1 file (~5KB) instead of 7 files (~35KB) = **86% reduction**

## Strategy YAML

!!! info "YAML vs Entry Point Detection"
    With the new entry point detection (Story 001), `strategy.yaml` is primarily needed for **multi-file strategies**. Single-file strategies work automatically with zero configuration!

### When to Use

Use `strategy.yaml` when you need to:
- **Capture multi-file strategies** (entry point + imported modules)
- Capture non-Python files (JSON, CSV, YAML)
- Include data files or configuration
- Override entry point detection
- Have precise control over captured artifacts

### Basic Usage

Create `strategy.yaml` in your strategy directory:

```yaml
# strategy.yaml
files:
  - my_strategy.py
  - utils/indicators.py
  - utils/risk.py
  - config/params.json
  - data/reference_data.csv
```

**Path rules:**
- Paths relative to `strategy.yaml` location
- Use forward slashes `/` (works on all platforms)
- Can use `../` for parent directories

### Complete Example

**Project structure:**
```
trading_project/
├── strategy.yaml
├── strategies/
│   ├── main_strategy.py
│   └── fallback_strategy.py
├── indicators/
│   ├── technical.py
│   └── custom.py
├── config/
│   ├── params.json
│   ├── asset_universe.csv
│   └── factor_weights.yaml
└── data/
    └── reference_prices.parquet
```

**strategy.yaml:**
```yaml
# Strategy: Multi-Factor Mean Reversion
# Version: 2.1.0
# Author: Quant Team

files:
  # Core strategy files
  - strategies/main_strategy.py
  - strategies/fallback_strategy.py

  # Indicator modules
  - indicators/technical.py
  - indicators/custom.py

  # Configuration files
  - config/params.json
  - config/asset_universe.csv
  - config/factor_weights.yaml

  # Reference data
  - data/reference_prices.parquet

# Optional metadata (not used by system, for documentation)
metadata:
  strategy_name: "Multi-Factor Mean Reversion"
  version: "2.1.0"
  author: "Quant Team"
  description: "Factor-based mean reversion with dynamic position sizing"
```

**Captured structure:**
```
backtests/20251019_143527_123/code/
├── strategy.yaml
├── strategies/
│   ├── main_strategy.py
│   └── fallback_strategy.py
├── indicators/
│   ├── technical.py
│   └── custom.py
├── config/
│   ├── params.json
│   ├── asset_universe.csv
│   └── factor_weights.yaml
└── data/
    └── reference_prices.parquet
```

### Advanced YAML Features

**Wildcards (future feature):**
```yaml
files:
  - strategies/*.py
  - indicators/**/*.py  # Recursive
  - config/*.{json,yaml}
```

**Exclusions (future feature):**
```yaml
files:
  - strategies/*.py
exclude:
  - strategies/experimental_*.py
  - strategies/test_*.py
```

## Configuration

### Global Configuration

Set default code capture mode in your configuration:

```python
# config.py
BACKTEST_OUTPUT = {
    'enabled': True,
    'base_dir': 'backtests',
    'code_capture_mode': 'import_analysis',  # or 'strategy_yaml'
}
```

### Per-Backtest Override

Override at runtime:

```python
from rustybt import run_algorithm
from rustybt.backtest import BacktestArtifactManager

# Create artifact manager with specific mode
manager = BacktestArtifactManager(
    base_dir='backtests',
    code_capture_mode='strategy_yaml'
)

# Run with custom configuration
result = run_algorithm(
    # ... parameters
    artifact_manager=manager
)
```

### Disable Code Capture

For rapid iteration during development:

```python
# Disable code capture temporarily
manager = BacktestArtifactManager(
    base_dir='backtests',
    code_capture_mode=None  # Disable
)
```

## Best Practices

### 1. Organize Imports

Keep imports organized for better capture:

```python
# my_strategy.py

# Standard library
import os
from datetime import datetime

# Third-party
import numpy as np
import pandas as pd

# Framework
from rustybt import order, symbol

# Local modules (these get captured)
from .indicators import calculate_rsi
from .risk import position_sizer
```

### 2. Use Relative Imports

For portable strategies, use relative imports:

```python
# ✅ Good - portable
from .utils.indicators import calculate_rsi

# ❌ Avoid - depends on Python path
from utils.indicators import calculate_rsi
```

### 3. Document Dependencies

Include a requirements file:

```yaml
# strategy.yaml
files:
  - my_strategy.py
  - utils/indicators.py
  - requirements.txt  # Capture dependencies
  - README.md         # Capture documentation
```

### 4. Version Strategy Code

Include version information:

```python
# my_strategy.py
"""
Momentum Strategy
Version: 2.1.0
Last Updated: 2025-10-19
"""

__version__ = '2.1.0'

def initialize(context):
    context.strategy_version = __version__
    # ...
```

### 5. Configuration as Code

Use configuration files for parameters:

```json
// config/params.json
{
  "rsi_period": 14,
  "rsi_threshold_low": 30,
  "rsi_threshold_high": 70,
  "position_size_pct": 0.1,
  "max_positions": 10
}
```

```python
# my_strategy.py
import json
from pathlib import Path

def initialize(context):
    # Load configuration
    config_path = Path(__file__).parent / 'config' / 'params.json'
    with open(config_path) as f:
        params = json.load(f)

    context.rsi_period = params['rsi_period']
    # ...
```

## Troubleshooting

### Missing Files

**Problem:** Expected files not captured

**Diagnosis:**
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check captured files in metadata
import json
metadata_path = f"{result.output_dir}/metadata/backtest_metadata.json"
with open(metadata_path) as f:
    metadata = json.load(f)

print("Captured files:")
for file in metadata['captured_files']:
    print(f"  - {file}")
```

**Solutions:**
1. Verify imports are static (not dynamic)
2. Check import paths are correct
3. Use `strategy.yaml` for explicit control

### Dynamic Imports

**Problem:** Using `importlib` for dynamic imports

**Solution:** Use `strategy.yaml` to explicitly list files:

```yaml
# strategy.yaml
files:
  - my_strategy.py
  - plugins/plugin_a.py
  - plugins/plugin_b.py
```

### Large Projects

**Problem:** Code capture takes too long

**Optimization:**

1. **Use strategy.yaml** - Only capture necessary files
2. **Exclude test files** - Don't capture tests
3. **Disable during dev** - Only enable for production runs

```yaml
# strategy.yaml - optimized
files:
  # Core strategy only
  - strategies/production_strategy.py
  - indicators/core_indicators.py

  # Exclude test files, examples, docs
  # Exclude __pycache__, .pyc files
```

### Permission Errors

**Problem:** Cannot copy certain files

**Solution:**
1. Check file permissions
2. Verify files exist and are readable
3. Check disk space in output directory

## Examples

### Example 1: Simple Single-File Strategy

```python
# simple_strategy.py
from rustybt import order, symbol

def initialize(context):
    context.asset = symbol('AAPL')
    context.threshold = 0.02

def handle_data(context, data):
    price = data.current(context.asset, 'price')
    if price_changed(price, context.threshold):
        order(context.asset, 10)
```

**Captured:**
- `simple_strategy.py`

No `strategy.yaml` needed!

### Example 2: Multi-Module Strategy

```python
# strategies/momentum.py
from indicators.technical import RSI, MACD
from risk.manager import RiskManager

class MomentumStrategy:
    def __init__(self):
        self.rsi = RSI(period=14)
        self.macd = MACD()
        self.risk_mgr = RiskManager(max_position_pct=0.1)

    def on_data(self, data):
        # Strategy logic
        pass
```

**Auto-captured:**
- `strategies/momentum.py`
- `indicators/technical.py`
- `risk/manager.py`

### Example 3: Configuration-Driven Strategy

**Project structure:**
```
quant_strategy/
├── strategy.yaml
├── main.py
├── config/
│   ├── symbols.json
│   └── params.yaml
└── modules/
    ├── factors.py
    └── portfolio.py
```

**strategy.yaml:**
```yaml
files:
  - main.py
  - config/symbols.json
  - config/params.yaml
  - modules/factors.py
  - modules/portfolio.py
```

**main.py:**
```python
import yaml
import json
from pathlib import Path

def load_config():
    """Load strategy configuration."""
    base_path = Path(__file__).parent

    with open(base_path / 'config' / 'params.yaml') as f:
        params = yaml.safe_load(f)

    with open(base_path / 'config' / 'symbols.json') as f:
        symbols = json.load(f)

    return params, symbols

def initialize(context):
    params, symbols = load_config()
    context.params = params
    context.universe = symbols
```

All configuration files are captured along with code!

## Performance

### Entry Point Detection (NEW DEFAULT)

**Capture Time:** < 50ms (1 file copy)

**Storage Savings:**

| Optimization Run Size | Old (Import Analysis) | New (Entry Point) | Reduction |
|----------------------|----------------------|-------------------|-----------|
| 10 runs | 500 KB (100 files) | 50 KB (10 files) | **90%** |
| 36 runs | 1.8 MB (360 files) | 180 KB (36 files) | **90%** |
| 100 runs | 5 MB (1000 files) | 500 KB (100 files) | **90%** |
| 1000 runs | 50 MB (10000 files) | 5 MB (1000 files) | **90%** |

### YAML-Based Capture

| Project Size | Files | Capture Time |
|--------------|-------|--------------|
| Small (1-5 files) | 5 | < 100ms |
| Medium (10-20 files) | 20 | < 500ms |
| Large (50+ files) | 50 | < 2s |
| Very Large (200+ files) | 200 | < 5s |

**Optimization tips:**
- **Default (entry point):** Perfect for optimization runs - no action needed!
- **Multi-file strategies:** Use `strategy.yaml` to capture dependencies
- **Large projects:** Use `strategy.yaml` to exclude unnecessary files
- **Development:** Disable capture for rapid iteration

## See Also

- [Backtest Output Organization](backtest-output-organization.md) - Overall backtest output system
- [DataCatalog](../api/data-management/catalog/README.md) - Data provenance tracking
- [API Reference: StrategyCodeCapture](../api/backtest/code-capture.md) - API documentation
