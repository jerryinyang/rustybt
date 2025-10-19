# BacktestArtifactManager API Reference

## Overview

The `BacktestArtifactManager` class manages the organization and storage of backtest outputs, including results, strategy code, and metadata. It provides a centralized system for artifact management with automatic directory creation, path resolution, and metadata tracking.

## Class Definition

```python
from rustybt.backtest import BacktestArtifactManager

manager = BacktestArtifactManager(
    base_dir='backtests',
    code_capture_mode='import_analysis'
)
```

## Constructor

### `BacktestArtifactManager.__init__`

```python
def __init__(
    self,
    base_dir: str | Path = 'backtests',
    code_capture_mode: str | None = 'import_analysis',
    backtest_id: str | None = None
)
```

Initialize a new backtest artifact manager.

**Parameters:**

- **`base_dir`** (`str | Path`, default: `'backtests'`)<br>
  Base directory for all backtest outputs. Created if doesn't exist.

- **`code_capture_mode`** (`str | None`, default: `'import_analysis'`)<br>
  Code capture method:
  - `'import_analysis'`: Automatic via import analysis
  - `'strategy_yaml'`: Explicit via strategy.yaml
  - `None`: Disable code capture

- **`backtest_id`** (`str | None`, default: `None`)<br>
  Custom backtest ID. If `None`, generates timestamp-based ID.

**Raises:**

- **`ValueError`**: Invalid `code_capture_mode`
- **`OSError`**: Cannot create or access `base_dir`

**Example:**

```python
# Default configuration
manager = BacktestArtifactManager()

# Custom directory
manager = BacktestArtifactManager(base_dir='my_backtests')

# Disable code capture
manager = BacktestArtifactManager(code_capture_mode=None)

# Custom backtest ID
manager = BacktestArtifactManager(backtest_id='test_run_001')
```

## Properties

### `backtest_id`

```python
@property
def backtest_id(self) -> str
```

Get the unique backtest identifier.

**Returns:** Timestamp-based ID in format `YYYYMMDD_HHMMSS_mmm`

**Example:**

```python
manager = BacktestArtifactManager()
print(manager.backtest_id)  # '20251019_143527_123'
```

---

### `output_dir`

```python
@property
def output_dir(self) -> Path
```

Get the main output directory for this backtest.

**Returns:** Path to `{base_dir}/{backtest_id}/`

**Example:**

```python
manager = BacktestArtifactManager()
print(manager.output_dir)  # Path('backtests/20251019_143527_123')
```

---

### `results_dir`

```python
@property
def results_dir(self) -> Path
```

Get the results subdirectory.

**Returns:** Path to `{output_dir}/results/`

**Example:**

```python
path = manager.results_dir
print(path)  # Path('backtests/20251019_143527_123/results')
```

---

### `code_dir`

```python
@property
def code_dir(self) -> Path
```

Get the code subdirectory.

**Returns:** Path to `{output_dir}/code/`

**Example:**

```python
path = manager.code_dir
print(path)  # Path('backtests/20251019_143527_123/code')
```

---

### `metadata_dir`

```python
@property
def metadata_dir(self) -> Path
```

Get the metadata subdirectory.

**Returns:** Path to `{output_dir}/metadata/`

**Example:**

```python
path = manager.metadata_dir
print(path)  # Path('backtests/20251019_143527_123/metadata')
```

## Methods

### `initialize`

```python
def initialize(self) -> None
```

Initialize the backtest output directory structure.

Creates:
- Main output directory
- `results/` subdirectory
- `code/` subdirectory
- `metadata/` subdirectory

**Raises:**

- **`OSError`**: Cannot create directories
- **`PermissionError`**: Insufficient permissions

**Example:**

```python
manager = BacktestArtifactManager()
manager.initialize()

# Directory structure created:
# backtests/20251019_143527_123/
#   ├── results/
#   ├── code/
#   └── metadata/
```

---

### `capture_strategy_code`

```python
def capture_strategy_code(
    self,
    strategy_path: str | Path,
    strategy_yaml_path: str | Path | None = None
) -> list[str]
```

Capture strategy source code files.

**Parameters:**

- **`strategy_path`** (`str | Path`)<br>
  Path to main strategy file

- **`strategy_yaml_path`** (`str | Path | None`, default: `None`)<br>
  Path to strategy.yaml (overrides auto-detection)

**Returns:** List of captured file paths (relative to code_dir)

**Raises:**

- **`FileNotFoundError`**: Strategy file not found
- **`ValueError`**: Invalid strategy path

**Example:**

```python
manager = BacktestArtifactManager()
manager.initialize()

# Capture with import analysis
files = manager.capture_strategy_code('my_strategy.py')
print(files)
# ['my_strategy.py', 'utils/indicators.py', 'utils/risk.py']

# Capture with explicit YAML
files = manager.capture_strategy_code(
    strategy_path='my_strategy.py',
    strategy_yaml_path='strategy.yaml'
)
```

---

### `save_metadata`

```python
def save_metadata(
    self,
    metadata: dict[str, Any]
) -> Path
```

Save backtest metadata to JSON file.

**Parameters:**

- **`metadata`** (`dict[str, Any]`)<br>
  Metadata dictionary to save

**Returns:** Path to saved metadata file

**Raises:**

- **`OSError`**: Cannot write file
- **`ValueError`**: Invalid metadata format

**Example:**

```python
metadata = {
    'backtest_id': manager.backtest_id,
    'timestamp': datetime.now().isoformat(),
    'framework_version': '0.2.0',
    'strategy_params': {
        'capital_base': 10000,
        'start_date': '2020-01-01'
    }
}

path = manager.save_metadata(metadata)
print(path)  # Path('backtests/20251019_143527_123/metadata/backtest_metadata.json')
```

---

### `get_result_path`

```python
def get_result_path(
    self,
    filename: str,
    subfolder: str | None = None
) -> Path
```

Get path for saving a result file.

**Parameters:**

- **`filename`** (`str`)<br>
  Name of the result file

- **`subfolder`** (`str | None`, default: `None`)<br>
  Optional subfolder within results directory

**Returns:** Full path for the result file

**Example:**

```python
# Simple result file
path = manager.get_result_path('backtest_results.csv')
print(path)  # Path('backtests/20251019_143527_123/results/backtest_results.csv')

# With subfolder
path = manager.get_result_path('report.html', subfolder='reports')
print(path)  # Path('backtests/20251019_143527_123/results/reports/report.html')
```

---

### `link_backtest_to_bundles`

```python
def link_backtest_to_bundles(
    self,
    catalog: DataCatalog | None = None
) -> list[str]
```

Link backtest to data bundles used.

**Parameters:**

- **`catalog`** (`DataCatalog | None`, default: `None`)<br>
  DataCatalog instance. If `None`, creates new instance.

**Returns:** List of bundle names linked to this backtest

**Raises:**

- **`RuntimeError`**: DataCatalog not available

**Example:**

```python
from rustybt.data.catalog import DataCatalog

catalog = DataCatalog()
manager = BacktestArtifactManager()

# Link backtest to bundles
bundles = manager.link_backtest_to_bundles(catalog)
print(bundles)  # ['quandl', 'custom_data']
```

---

### `load_metadata`

```python
def load_metadata(self) -> dict[str, Any]
```

Load backtest metadata from file.

**Returns:** Metadata dictionary

**Raises:**

- **`FileNotFoundError`**: Metadata file doesn't exist
- **`json.JSONDecodeError`**: Invalid JSON format

**Example:**

```python
manager = BacktestArtifactManager(backtest_id='20251019_143527_123')
metadata = manager.load_metadata()

print(metadata['framework_version'])  # '0.2.0'
print(metadata['captured_files'])     # ['my_strategy.py', ...]
```

---

### `list_result_files`

```python
def list_result_files(self) -> list[Path]
```

List all result files in the backtest directory.

**Returns:** List of paths to result files

**Example:**

```python
manager = BacktestArtifactManager(backtest_id='20251019_143527_123')
files = manager.list_result_files()

for file in files:
    print(file.name, file.stat().st_size)
# backtest_results.csv 376000
# backtest_results.parquet 85000
# summary_statistics.csv 167
```

## Class Methods

### `generate_backtest_id`

```python
@classmethod
def generate_backtest_id(cls) -> str
```

Generate a unique timestamp-based backtest ID.

**Returns:** Backtest ID in format `YYYYMMDD_HHMMSS_mmm`

**Example:**

```python
backtest_id = BacktestArtifactManager.generate_backtest_id()
print(backtest_id)  # '20251019_143527_123'
```

---

### `from_backtest_id`

```python
@classmethod
def from_backtest_id(
    cls,
    backtest_id: str,
    base_dir: str | Path = 'backtests'
) -> BacktestArtifactManager
```

Create manager instance from existing backtest ID.

**Parameters:**

- **`backtest_id`** (`str`)<br>
  Existing backtest identifier

- **`base_dir`** (`str | Path`, default: `'backtests'`)<br>
  Base directory containing backtest

**Returns:** Configured BacktestArtifactManager instance

**Raises:**

- **`FileNotFoundError`**: Backtest directory doesn't exist

**Example:**

```python
# Load existing backtest
manager = BacktestArtifactManager.from_backtest_id('20251019_143527_123')

# Access existing backtest data
metadata = manager.load_metadata()
results = manager.list_result_files()
```

## Integration with TradingAlgorithm

The artifact manager is automatically integrated with `TradingAlgorithm`:

```python
from rustybt import TradingAlgorithm

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Access artifact manager
        manager = self.artifact_manager

        print(f"Backtest ID: {manager.backtest_id}")
        print(f"Output dir: {manager.output_dir}")

    def handle_data(self, context, data):
        # Save custom artifacts
        custom_path = self.artifact_manager.get_result_path('custom_data.csv')
        # ... save custom data
```

## Usage Examples

### Example 1: Basic Backtest Output

```python
from rustybt import run_algorithm
from datetime import datetime
import pytz

# Run backtest
result = run_algorithm(
    start=datetime(2020, 1, 1, tzinfo=pytz.UTC),
    end=datetime(2023, 12, 31, tzinfo=pytz.UTC),
    initialize=initialize,
    handle_data=handle_data,
    capital_base=10000,
    bundle='quandl'
)

# Access artifact manager
manager = result.artifact_manager

# Get output paths
print(f"Backtest ID: {manager.backtest_id}")
print(f"Results directory: {manager.results_dir}")
print(f"Code directory: {manager.code_dir}")
print(f"Metadata directory: {manager.metadata_dir}")
```

### Example 2: Custom Artifact Storage

```python
from rustybt import TradingAlgorithm
import pandas as pd

class CustomStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.custom_metrics = []

    def handle_data(self, context, data):
        # Track custom metrics
        metric = calculate_custom_metric(data)
        context.custom_metrics.append(metric)

    def analyze(self, context, perf):
        # Save custom metrics at end of backtest
        df = pd.DataFrame(context.custom_metrics)

        # Use artifact manager to get proper path
        custom_path = self.artifact_manager.get_result_path(
            'custom_metrics.csv',
            subfolder='analytics'
        )

        # Ensure directory exists
        custom_path.parent.mkdir(parents=True, exist_ok=True)

        # Save custom data
        df.to_csv(custom_path, index=False)
        print(f"Custom metrics saved to: {custom_path}")
```

### Example 3: Programmatic Backtest Comparison

```python
from rustybt.backtest import BacktestArtifactManager
import pandas as pd

def compare_backtests(backtest_ids: list[str]) -> pd.DataFrame:
    """Compare multiple backtests."""
    results = []

    for backtest_id in backtest_ids:
        # Load backtest
        manager = BacktestArtifactManager.from_backtest_id(backtest_id)

        # Load metadata
        metadata = manager.load_metadata()

        # Load results
        results_path = manager.get_result_path('backtest_results.parquet')
        perf = pd.read_parquet(results_path)

        # Extract metrics
        results.append({
            'backtest_id': backtest_id,
            'timestamp': metadata['timestamp'],
            'framework_version': metadata['framework_version'],
            'total_return': perf['returns'].sum(),
            'sharpe_ratio': calculate_sharpe(perf['returns']),
            'max_drawdown': perf['max_drawdown'].min()
        })

    return pd.DataFrame(results)

# Compare recent backtests
comparison = compare_backtests([
    '20251019_143527_123',
    '20251019_145821_456',
    '20251019_151234_789'
])

print(comparison)
```

### Example 4: Cleanup Old Backtests

```python
from rustybt.backtest import BacktestArtifactManager
from datetime import datetime, timedelta
import shutil
from pathlib import Path

def cleanup_old_backtests(base_dir='backtests', days=90):
    """Remove backtests older than specified days."""
    cutoff = datetime.now() - timedelta(days=days)
    base_path = Path(base_dir)

    for backtest_dir in base_path.iterdir():
        if not backtest_dir.is_dir():
            continue

        # Parse backtest ID timestamp
        backtest_id = backtest_dir.name
        try:
            # Format: YYYYMMDD_HHMMSS_mmm
            date_str = backtest_id.split('_')[0]
            backtest_date = datetime.strptime(date_str, '%Y%m%d')

            if backtest_date < cutoff:
                print(f"Removing old backtest: {backtest_id}")
                shutil.rmtree(backtest_dir)

        except (ValueError, IndexError):
            print(f"Skipping invalid backtest directory: {backtest_id}")

# Remove backtests older than 90 days
cleanup_old_backtests(days=90)
```

## Thread Safety

The `BacktestArtifactManager` uses thread-safe ID generation:

```python
import threading
from rustybt.backtest import BacktestArtifactManager

def run_backtest(thread_id):
    """Run backtest in separate thread."""
    manager = BacktestArtifactManager()
    print(f"Thread {thread_id}: {manager.backtest_id}")
    # Each thread gets unique ID even if created simultaneously

# Run concurrent backtests
threads = []
for i in range(10):
    t = threading.Thread(target=run_backtest, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

# All backtest IDs are unique
```

## See Also

- [Backtest Output Organization Guide](../../guides/backtest-output-organization.md)
- [Strategy Code Capture Guide](../../guides/strategy-code-capture.md)
- [StrategyCodeCapture API](code-capture.md)
- [DataCatalog API](../data-management/catalog/catalog-api.md)
