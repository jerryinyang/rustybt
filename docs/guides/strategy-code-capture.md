# Strategy Code Capture

## Overview

RustyBT automatically captures your strategy source code during backtest execution, ensuring complete reproducibility. Whether you're running simple single-file strategies or complex multi-module projects, your code is preserved for future reference and auditing.

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

RustyBT supports two code capture methods:

### 1. Import Analysis (Automatic)

**Default method** - analyzes import statements to discover strategy files.

**Pros:**
- Zero configuration required
- Works automatically
- Captures only relevant files

**Cons:**
- Only captures Python files
- Requires static imports (no dynamic loading)

### 2. Strategy YAML (Explicit)

**Manual method** - explicitly specify files to capture.

**Pros:**
- Capture any file type (JSON, CSV, YAML, etc.)
- Full control over captured files
- Works with dynamic imports

**Cons:**
- Requires manual configuration
- Need to update when adding files

## Import Analysis

### How It Works

The system analyzes your strategy's import statements using Python's Abstract Syntax Tree (AST):

```python
# my_strategy.py
from utils.indicators import calculate_rsi, calculate_macd
from utils.risk import position_sizer
import config.params as params

def initialize(context):
    context.params = params
```

**Captured files:**
- `my_strategy.py`
- `utils/indicators.py`
- `utils/risk.py`
- `config/params.py`

**Excluded automatically:**
- Framework code: `rustybt.*`
- Standard library: `os`, `sys`, `datetime`, etc.
- Third-party packages: `numpy`, `pandas`, `ccxt`, etc.

### Supported Import Patterns

✅ **Absolute imports:**
```python
import utils.indicators
from utils.indicators import calculate_rsi
```

✅ **Relative imports:**
```python
from .utils import indicators
from ..shared.helpers import utility_function
```

✅ **Aliased imports:**
```python
import utils.indicators as ind
from utils import indicators as ind
```

✅ **Multiple imports:**
```python
from utils.indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger
)
```

❌ **Not supported:**
```python
# Dynamic imports
importlib.import_module('utils.indicators')

# Conditional imports (will warn but not fail)
if USE_ADVANCED:
    from advanced.indicators import special_indicator
```

### File Discovery

Import analysis discovers files by:

1. **Parsing imports** - Extract module names from AST
2. **Resolving paths** - Use Python's import system to locate files
3. **Filtering** - Exclude framework, stdlib, and third-party code
4. **Copying** - Preserve directory structure in output

### Example: Multi-Module Strategy

```
my_project/
├── strategies/
│   └── momentum_strategy.py       # Entry point
├── indicators/
│   ├── __init__.py
│   ├── technical.py
│   └── custom.py
├── risk/
│   ├── __init__.py
│   └── position_sizing.py
└── config/
    └── params.py
```

**momentum_strategy.py:**
```python
from indicators.technical import calculate_rsi
from indicators.custom import custom_momentum
from risk.position_sizing import calculate_position_size
from config import params

def initialize(context):
    context.rsi_threshold = params.RSI_THRESHOLD

def handle_data(context, data):
    rsi = calculate_rsi(data)
    momentum = custom_momentum(data)

    if rsi < context.rsi_threshold:
        size = calculate_position_size(context, data)
        order(context.asset, size)
```

**Captured structure:**
```
backtests/20251019_143527_123/code/
├── strategies/
│   └── momentum_strategy.py
├── indicators/
│   ├── __init__.py
│   ├── technical.py
│   └── custom.py
├── risk/
│   ├── __init__.py
│   └── position_sizing.py
└── config/
    └── params.py
```

## Strategy YAML

### When to Use

Use `strategy.yaml` when you need to:
- Capture non-Python files (JSON, CSV, YAML)
- Include data files or configuration
- Exclude files that would be auto-captured
- Handle dynamic imports
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

Code capture is designed to be fast:

| Project Size | Files | Capture Time |
|--------------|-------|--------------|
| Small (1-5 files) | 5 | < 100ms |
| Medium (10-20 files) | 20 | < 500ms |
| Large (50+ files) | 50 | < 2s |
| Very Large (200+ files) | 200 | < 5s |

**Optimization tips:**
- Use `strategy.yaml` for large projects
- Exclude unnecessary files
- Disable capture during development

## See Also

- [Backtest Output Organization](backtest-output-organization.md) - Overall backtest output system
- [DataCatalog](../api/data-management/catalog/README.md) - Data provenance tracking
- [API Reference: StrategyCodeCapture](../api/backtest/code-capture.md) - API documentation
