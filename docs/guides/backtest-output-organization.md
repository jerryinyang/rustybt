# Backtest Output Organization

## Overview

RustyBT automatically organizes all backtest outputs into timestamped directories, making it easy to track, compare, and reproduce your backtesting results. Every backtest run creates a dedicated folder containing results, strategy code, and metadata.

## Features

- **Automatic Organization**: All backtest outputs saved to timestamped directories
- **Code Capture**: Strategy source code automatically preserved for reproducibility
- **Metadata Tracking**: Complete provenance information including framework version, data sources, and timestamps
- **DataCatalog Integration**: Links backtests with cached datasets for efficient data management
- **Backward Compatible**: Works seamlessly with existing backtesting workflows

## Directory Structure

Each backtest creates a unique directory under `backtests/` with the following structure:

```
backtests/
└── 20251019_143527_123/           # YYYYMMDD_HHMMSS_mmm (timestamp with milliseconds)
    ├── results/
    │   ├── backtest_results.csv
    │   ├── backtest_results.parquet
    │   ├── summary_statistics.csv
    │   ├── optimization_results.csv
    │   └── reports/
    │       ├── basic_report.html
    │       └── advanced_report.html
    ├── code/
    │   ├── my_strategy.py
    │   └── utils/
    │       └── indicators.py
    └── metadata/
        └── backtest_metadata.json
```

### Directory Components

- **`results/`**: All backtest outputs (CSV, Parquet, reports)
- **`code/`**: Captured strategy source code
- **`metadata/`**: Backtest metadata and provenance information

## Basic Usage

### Running a Backtest

No code changes are required! Simply run your backtest as usual:

```python
from rustybt import run_algorithm
from datetime import datetime
import pytz

# Your strategy implementation
def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    order(context.asset, 10)

# Run backtest - outputs automatically organized
result = run_algorithm(
    start=datetime(2020, 1, 1, tzinfo=pytz.UTC),
    end=datetime(2023, 12, 31, tzinfo=pytz.UTC),
    initialize=initialize,
    handle_data=handle_data,
    capital_base=10000,
    bundle='quandl'
)

# Access the backtest output directory
print(f"Results saved to: {result.backtest_id}")
```

### Accessing Backtest Results

The backtest ID is logged to the console and available as an attribute:

```python
# Get the backtest ID from the result
backtest_id = result.backtest_id
print(f"Backtest ID: {backtest_id}")

# Access output directory path
output_dir = result.output_dir
print(f"Output directory: {output_dir}")

# List all result files
import os
results_dir = os.path.join(output_dir, 'results')
print(os.listdir(results_dir))
```

## Strategy Code Capture

RustyBT automatically captures your strategy code for reproducibility using two methods:

### 1. Import Analysis (Default)

The system automatically detects and copies all strategy files by analyzing import statements:

```python
# my_strategy.py
from .utils.indicators import calculate_rsi
from .utils.risk import position_sizer

def initialize(context):
    context.rsi_threshold = 30

def handle_data(context, data):
    rsi = calculate_rsi(data)
    size = position_sizer(context, rsi)
    # ... trading logic
```

**Captured files:**
- `my_strategy.py`
- `utils/indicators.py`
- `utils/risk.py`

The system intelligently excludes:
- Framework code (`rustybt.*`)
- Standard library modules
- Third-party packages (`numpy`, `pandas`, etc.)

### 2. Explicit Configuration (strategy.yaml)

For complex projects or precise control, create a `strategy.yaml` file:

```yaml
# strategy.yaml
files:
  - my_strategy.py
  - utils/indicators.py
  - utils/risk.py
  - config/params.json
  - data/reference_data.csv
```

Place `strategy.yaml` in the same directory as your strategy entry point. The system will use it automatically.

**Benefits:**
- Include non-Python files (JSON, CSV, etc.)
- Exclude files you don't want captured
- Full control over captured artifacts

See [Strategy Code Capture Guide](strategy-code-capture.md) for detailed examples.

## Backtest Metadata

Each backtest generates a `backtest_metadata.json` file with complete provenance information:

```json
{
  "backtest_id": "20251019_143527_123",
  "timestamp": "2025-10-19T14:35:27.123Z",
  "framework_version": "0.2.0",
  "python_version": "3.12.1",
  "strategy_entry_point": "/path/to/my_strategy.py",
  "captured_files": [
    "my_strategy.py",
    "utils/indicators.py"
  ],
  "data_bundle_info": {
    "bundle_name": "quandl",
    "dataset_ids": ["uuid-dataset-1", "uuid-dataset-2"]
  },
  "algorithm_params": {
    "capital_base": 10000,
    "start_date": "2020-01-01T00:00:00+00:00",
    "end_date": "2023-12-31T00:00:00+00:00"
  }
}
```

### Metadata Fields

| Field | Description |
|-------|-------------|
| `backtest_id` | Unique timestamp-based identifier |
| `timestamp` | ISO 8601 timestamp of backtest execution |
| `framework_version` | RustyBT version used |
| `python_version` | Python interpreter version |
| `strategy_entry_point` | Path to main strategy file |
| `captured_files` | List of all captured source files |
| `data_bundle_info` | Information about data bundles used |
| `algorithm_params` | Backtest configuration parameters |

## Configuration

Configure backtest output behavior in your configuration file:

```python
# config.py or rustybt_config.yaml
backtest_output = {
    'enabled': True,  # Enable/disable output organization
    'base_dir': 'backtests',  # Base directory for outputs
    'code_capture_mode': 'import_analysis',  # or 'strategy_yaml'
}
```

### Configuration Options

- **`enabled`** (default: `True`): Enable/disable automatic output organization
- **`base_dir`** (default: `'backtests'`): Base directory for backtest outputs
- **`code_capture_mode`** (default: `'import_analysis'`): Method for capturing strategy code
  - `'import_analysis'`: Automatic detection via import analysis
  - `'strategy_yaml'`: Use explicit `strategy.yaml` specification

## Jupyter Notebook Integration

The backtest output system works seamlessly in Jupyter notebooks:

```python
# In Jupyter notebook
from rustybt import run_algorithm

result = run_algorithm(
    # ... your backtest parameters
)

# Display backtest ID in notebook
from IPython.display import display, Markdown
display(Markdown(f"**Backtest ID:** `{result.backtest_id}`"))
display(Markdown(f"**Output Directory:** `{result.output_dir}`"))

# Load results directly
import pandas as pd
results_path = f"{result.output_dir}/results/backtest_results.parquet"
df = pd.read_parquet(results_path)
df.head()
```

## DataCatalog Integration

Backtests are automatically linked to their data sources in the DataCatalog:

```python
from rustybt.data.catalog import DataCatalog

# Initialize catalog
catalog = DataCatalog()

# Get datasets used in a backtest
datasets = catalog.get_backtest_datasets(backtest_id='20251019_143527_123')

for dataset in datasets:
    print(f"Dataset: {dataset.name}")
    print(f"  Bundle: {dataset.bundle_name}")
    print(f"  Cached: {dataset.cache_path}")
```

This linkage enables:
- **Data Provenance**: Track which data produced which results
- **Cache Reuse**: Identify backtests using the same data
- **Reproducibility**: Ensure data consistency across runs

## Advanced Usage

### Custom Output Directory

Override the default output location:

```python
from rustybt.backtest import BacktestArtifactManager

# Create custom artifact manager
manager = BacktestArtifactManager(base_dir='custom/path/backtests')

# Run algorithm with custom manager
result = run_algorithm(
    # ... parameters
    artifact_manager=manager
)
```

### Accessing Artifact Manager

Get direct access to the artifact manager during execution:

```python
def initialize(context):
    # Access artifact manager
    manager = context.artifact_manager

    # Get output paths
    print(f"Results dir: {manager.results_dir}")
    print(f"Code dir: {manager.code_dir}")
    print(f"Metadata dir: {manager.metadata_dir}")
```

### Programmatic Result Loading

Load backtest results programmatically:

```python
import os
import json
import pandas as pd

def load_backtest(backtest_id, base_dir='backtests'):
    """Load backtest results and metadata."""
    backtest_dir = os.path.join(base_dir, backtest_id)

    # Load metadata
    metadata_path = os.path.join(backtest_dir, 'metadata', 'backtest_metadata.json')
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    # Load results
    results_path = os.path.join(backtest_dir, 'results', 'backtest_results.parquet')
    results = pd.read_parquet(results_path)

    return {
        'metadata': metadata,
        'results': results,
        'backtest_dir': backtest_dir
    }

# Usage
backtest = load_backtest('20251019_143527_123')
print(backtest['metadata']['framework_version'])
print(backtest['results'].head())
```

## Performance Considerations

The backtest output system is designed for minimal overhead:

- **Directory Creation**: < 100ms
- **Code Capture**: < 5 seconds for typical projects
- **Metadata Generation**: < 1 second
- **Total Overhead**: < 2% of backtest execution time

### Large Projects

For projects with many files:

1. Use `strategy.yaml` to explicitly specify files
2. Exclude unnecessary files (tests, docs, etc.)
3. Consider disabling code capture for rapid iteration:

```python
# Disable code capture during development
config = {
    'backtest_output': {
        'code_capture_mode': None  # Disable code capture
    }
}
```

## Troubleshooting

### Output Directory Not Created

**Problem**: Backtest runs but no output directory created

**Solution**:
1. Check that `backtest_output.enabled = True` in configuration
2. Verify write permissions on the `backtests/` directory
3. Check logs for error messages

### Missing Code Files

**Problem**: Some strategy files not captured

**Solution**:
1. Ensure imports use relative or absolute paths (not dynamic)
2. Create `strategy.yaml` to explicitly list files
3. Check import patterns are supported:
   - ✅ `from .utils import helper`
   - ✅ `import utils.helper`
   - ❌ `importlib.import_module('utils.helper')`

### DataCatalog Not Available

**Problem**: Warning "DataCatalog integration unavailable"

**Solution**: This is normal if you haven't set up the DataCatalog. The backtest will still run successfully, just without data linkage.

## Best Practices

### 1. Use Descriptive Strategy Names

Name your strategy files descriptively:
```
strategies/
  ├── momentum_rsi_strategy.py
  ├── mean_reversion_bollinger.py
  └── pairs_trading_cointegration.py
```

### 2. Version Control Strategy Code

Keep strategy code in version control separately from backtest results:
```
.gitignore:
  backtests/      # Exclude backtest results
  !backtests/.gitkeep
```

### 3. Document Strategy Parameters

Include parameter documentation in metadata:
```python
def initialize(context):
    """
    Strategy: RSI Mean Reversion

    Parameters:
    - RSI Period: 14
    - RSI Threshold: 30/70
    - Position Size: 10% of portfolio
    """
    context.rsi_period = 14
    # ...
```

### 4. Regular Cleanup

Implement a retention policy for old backtests:
```python
import os
import time
from datetime import datetime, timedelta

def cleanup_old_backtests(base_dir='backtests', days=90):
    """Remove backtests older than specified days."""
    cutoff = datetime.now() - timedelta(days=days)

    for backtest_id in os.listdir(base_dir):
        # Parse timestamp from backtest_id
        timestamp_str = backtest_id.split('_')[0]  # YYYYMMDD
        timestamp = datetime.strptime(timestamp_str, '%Y%m%d')

        if timestamp < cutoff:
            backtest_path = os.path.join(base_dir, backtest_id)
            print(f"Removing old backtest: {backtest_id}")
            # shutil.rmtree(backtest_path)  # Uncomment to actually delete
```

### 5. Compare Backtests

Use metadata for systematic comparison:
```python
def compare_backtests(backtest_ids):
    """Compare multiple backtests."""
    results = []

    for backtest_id in backtest_ids:
        data = load_backtest(backtest_id)
        results.append({
            'id': backtest_id,
            'version': data['metadata']['framework_version'],
            'sharpe': calculate_sharpe(data['results']),
            'total_return': calculate_total_return(data['results'])
        })

    return pd.DataFrame(results)
```

## Migration Guide

If you have existing backtesting code, no changes are required! The output organization system:

- ✅ Works with existing `run_algorithm()` calls
- ✅ Backward compatible with all APIs
- ✅ Does not break existing workflows
- ✅ Transparent to strategy code

Simply upgrade to v0.2.0+ and enjoy automatic output organization.

## See Also

- [Strategy Code Capture Guide](strategy-code-capture.md) - Detailed code capture documentation
- [DataCatalog Overview](../api/data-management/catalog/README.md) - Data catalog integration
- [API Reference: BacktestArtifactManager](../api/backtest/artifact-manager.md) - API documentation
- [API Reference: StrategyCodeCapture](../api/backtest/code-capture.md) - Code capture API
