# Backtest API Overview

## Introduction

The Backtest API provides tools for managing backtest execution, output organization, and artifact preservation. These components ensure reproducibility, traceability, and efficient management of backtesting workflows.

## Core Components

### BacktestArtifactManager

Manages the organization and storage of backtest outputs.

**Key Features:**
- Automatic timestamped directory creation
- Results, code, and metadata organization
- DataCatalog integration for data provenance
- Programmatic access to backtest artifacts

**Documentation:** [BacktestArtifactManager API](artifact-manager.md)

**Quick Example:**
```python
from rustybt.backtest import BacktestArtifactManager

manager = BacktestArtifactManager()
manager.initialize()

print(f"Backtest ID: {manager.backtest_id}")
print(f"Output directory: {manager.output_dir}")
```

### StrategyCodeCapture

Handles automatic discovery and preservation of strategy source code.

**Key Features:**
- Import analysis for automatic file discovery
- Strategy YAML for explicit configuration
- Preservation of directory structure
- Support for any file type

**Documentation:** [StrategyCodeCapture API](code-capture.md)

**Quick Example:**
```python
from rustybt.backtest import StrategyCodeCapture

capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir='backtests/20251019_143527_123/code'
)

captured_files = capturer.capture()
print(f"Captured {len(captured_files)} files")
```

## Integration with TradingAlgorithm

The backtest system is fully integrated with RustyBT's core execution engine:

```python
from rustybt import run_algorithm

def initialize(context):
    # Access artifact manager during backtest
    manager = context.artifact_manager
    print(f"Saving to: {manager.output_dir}")

def analyze(context, perf):
    # Save custom analysis
    custom_path = context.artifact_manager.get_result_path('analysis.csv')
    # ... save custom data

result = run_algorithm(
    initialize=initialize,
    analyze=analyze,
    # ... other parameters
)

# Access outputs after completion
print(f"Results in: {result.output_dir}")
```

## Directory Structure

Each backtest creates the following structure:

```
backtests/
└── 20251019_143527_123/           # Unique timestamp-based ID
    ├── results/                   # All backtest outputs
    │   ├── backtest_results.csv
    │   ├── backtest_results.parquet
    │   ├── summary_statistics.csv
    │   └── reports/               # Generated reports
    │       ├── basic_report.html
    │       └── advanced_report.html
    ├── code/                      # Strategy source code
    │   ├── my_strategy.py
    │   ├── utils/
    │   │   └── indicators.py
    │   └── config/
    │       └── params.json
    └── metadata/                  # Backtest metadata
        └── backtest_metadata.json
```

## Backtest Metadata

Every backtest generates comprehensive metadata:

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
    "dataset_ids": ["uuid-1", "uuid-2"]
  },
  "algorithm_params": {
    "capital_base": 10000,
    "start_date": "2020-01-01T00:00:00+00:00",
    "end_date": "2023-12-31T00:00:00+00:00"
  }
}
```

## Common Use Cases

### Use Case 1: Running a Backtest

```python
from rustybt import run_algorithm
from datetime import datetime
import pytz

result = run_algorithm(
    start=datetime(2020, 1, 1, tzinfo=pytz.UTC),
    end=datetime(2023, 12, 31, tzinfo=pytz.UTC),
    initialize=initialize,
    handle_data=handle_data,
    capital_base=10000
)

# Outputs automatically organized
print(f"Backtest ID: {result.backtest_id}")
```

### Use Case 2: Loading Past Results

```python
from rustybt.backtest import BacktestArtifactManager
import pandas as pd

# Load existing backtest
manager = BacktestArtifactManager.from_backtest_id('20251019_143527_123')

# Load metadata
metadata = manager.load_metadata()

# Load results
results_path = manager.get_result_path('backtest_results.parquet')
results = pd.read_parquet(results_path)
```

### Use Case 3: Comparing Multiple Backtests

```python
from rustybt.backtest import BacktestArtifactManager

def compare_backtests(backtest_ids):
    results = []
    for backtest_id in backtest_ids:
        manager = BacktestArtifactManager.from_backtest_id(backtest_id)
        metadata = manager.load_metadata()

        results.append({
            'id': backtest_id,
            'timestamp': metadata['timestamp'],
            'version': metadata['framework_version'],
            # ... extract more metrics
        })
    return results
```

### Use Case 4: Custom Artifact Storage

```python
from rustybt import TradingAlgorithm
import pandas as pd

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.custom_metrics = []

    def handle_data(self, context, data):
        # Collect custom metrics
        metric = calculate_custom_metric(data)
        context.custom_metrics.append(metric)

    def analyze(self, context, perf):
        # Save custom analysis
        df = pd.DataFrame(context.custom_metrics)

        custom_path = self.artifact_manager.get_result_path(
            'custom_metrics.csv',
            subfolder='analytics'
        )

        custom_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(custom_path, index=False)
```

## Configuration

Configure backtest output behavior globally:

```python
# config.py
BACKTEST_OUTPUT = {
    'enabled': True,                    # Enable output organization
    'base_dir': 'backtests',           # Base directory
    'code_capture_mode': 'import_analysis'  # or 'strategy_yaml'
}
```

Or override per-backtest:

```python
from rustybt.backtest import BacktestArtifactManager

manager = BacktestArtifactManager(
    base_dir='custom/backtests',
    code_capture_mode='strategy_yaml'
)

result = run_algorithm(
    # ... parameters
    artifact_manager=manager
)
```

## Best Practices

### 1. Use Descriptive IDs

While the system generates timestamp IDs automatically, you can add custom naming:

```python
manager = BacktestArtifactManager()
metadata = {
    'custom_name': 'momentum_strategy_v2_test',
    'description': 'Testing parameter optimization results'
}
manager.save_metadata(metadata)
```

### 2. Version Your Strategy Code

Include version information in your strategy:

```python
# my_strategy.py
__version__ = '2.1.0'

def initialize(context):
    context.strategy_version = __version__
```

### 3. Document Parameters

Save parameter information in metadata:

```python
metadata = {
    'strategy_params': {
        'rsi_period': 14,
        'threshold': 30,
        'position_size': 0.1
    }
}
```

### 4. Regular Cleanup

Implement retention policies for old backtests:

```python
from datetime import datetime, timedelta
import shutil

def cleanup_old_backtests(days=90):
    cutoff = datetime.now() - timedelta(days=days)
    # ... cleanup logic
```

### 5. Use DataCatalog Integration

Link backtests to data sources:

```python
manager = BacktestArtifactManager()
bundles = manager.link_backtest_to_bundles()
print(f"Linked to bundles: {bundles}")
```

## Performance

The backtest output system adds minimal overhead:

| Operation | Time |
|-----------|------|
| Directory creation | < 100ms |
| Code capture (10 files) | < 500ms |
| Metadata generation | < 1s |
| Total overhead | < 2% of backtest time |

## Thread Safety

- **BacktestArtifactManager**: Thread-safe ID generation
- **StrategyCodeCapture**: Create separate instances per thread

```python
import threading

def run_backtest(i):
    # Thread-safe: each thread gets unique ID
    manager = BacktestArtifactManager()
    # ... run backtest

threads = [threading.Thread(target=run_backtest, args=(i,)) for i in range(10)]
for t in threads:
    t.start()
```

## Migration Guide

Upgrading from pre-0.2.0 versions requires no code changes:

✅ **Backward Compatible**
- Existing `run_algorithm()` calls work unchanged
- No breaking API changes
- Transparent to strategy code

The output organization system activates automatically when you upgrade to v0.2.0+.

## Related Documentation

### User Guides
- [Backtest Output Organization](../../guides/backtest-output-organization.md) - Comprehensive user guide
- [Strategy Code Capture](../../guides/strategy-code-capture.md) - Code capture details

### API Reference
- [BacktestArtifactManager API](artifact-manager.md) - Full API documentation
- [StrategyCodeCapture API](code-capture.md) - Code capture API

### Related APIs
- [DataCatalog API](../data-management/catalog/README.md) - Data provenance
- [TradingAlgorithm API](../../api-reference.md) - Core execution engine

## Support

For issues or questions:
- GitHub Issues: [rustybt/issues](https://github.com/jerryinyang/rustybt/issues)
- Documentation: [docs.rustybt.io](https://jerryinyang.github.io/rustybt/)
