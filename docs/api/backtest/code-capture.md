# StrategyCodeCapture API Reference

## Overview

The `StrategyCodeCapture` class handles automatic discovery and copying of strategy source code files. It supports three capture modes:

1. **Entry point detection** (default) - Stores only the file containing `run_algorithm()` call
2. **Strategy.yaml** (explicit configuration) - Stores files listed in YAML
3. **Import analysis** (deprecated) - Automatically discovers all imported local modules

**New in v1.x**: Default behavior changed to entry point detection for storage efficiency during optimization runs.

## Class Definition

```python
from rustybt.backtest import StrategyCodeCapture

capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir='backtests/20251019_143527_123/code'
)
```

## Constructor

### `StrategyCodeCapture.__init__`

```python
def __init__(
    self,
    strategy_path: str | Path,
    output_dir: str | Path,
    mode: str = 'import_analysis'
)
```

Initialize a new strategy code capture instance.

**Parameters:**

- **`strategy_path`** (`str | Path`)<br>
  Path to the main strategy file

- **`output_dir`** (`str | Path`)<br>
  Directory where captured code will be stored

- **`mode`** (`str`, default: `'import_analysis'`)<br>
  Capture mode:
  - `'import_analysis'`: Automatic via import analysis
  - `'strategy_yaml'`: Explicit via strategy.yaml file

**Raises:**

- **`FileNotFoundError`**: Strategy file not found
- **`ValueError`**: Invalid capture mode
- **`OSError`**: Cannot access output directory

**Example:**

```python
# Import analysis mode (default)
capturer = StrategyCodeCapture(
    strategy_path='strategies/my_strategy.py',
    output_dir='backtests/20251019_143527_123/code'
)

# Strategy YAML mode
capturer = StrategyCodeCapture(
    strategy_path='strategies/my_strategy.py',
    output_dir='backtests/20251019_143527_123/code',
    mode='strategy_yaml'
)
```

## Data Classes

### `EntryPointDetectionResult`

```python
@dataclass
class EntryPointDetectionResult:
    detected_file: Path | None
    detection_method: str
    confidence: str
    warnings: list[str]
```

Result from entry point detection analysis.

**Attributes:**

- **`detected_file`** (`Path | None`)<br>
  Path to detected entry point file, or `None` if detection failed

- **`detection_method`** (`str`)<br>
  Method used for detection:
  - `'inspect_stack'`: Runtime stack introspection (most reliable)
  - `'ipython'`: Jupyter notebook detection
  - `'frozen'`: PyInstaller/frozen app detection
  - `'fallback'`: Best-effort detection

- **`confidence`** (`str`)<br>
  Confidence level: `'high'`, `'medium'`, `'low'`

- **`warnings`** (`list[str]`)<br>
  List of warnings encountered during detection

**Example:**

```python
from rustybt.backtest.code_capture import StrategyCodeCapture

capturer = StrategyCodeCapture()
result = capturer.detect_entry_point()

if result.detected_file:
    print(f"Entry point: {result.detected_file}")
    print(f"Method: {result.detection_method}")
    print(f"Confidence: {result.confidence}")
else:
    print("Detection failed")
    print(f"Warnings: {result.warnings}")
```

## Methods

### `detect_entry_point`

```python
def detect_entry_point(self) -> EntryPointDetectionResult
```

Detect the entry point file containing the `run_algorithm()` call using runtime introspection.

This method uses `inspect.stack()` to analyze the call stack and identify the file from which `run_algorithm()` was invoked. This is the core new feature in v1.x that enables storage-efficient code capture during optimization runs.

**Returns:** `EntryPointDetectionResult` with detection details

**Raises:** Does not raise exceptions - failures are captured in result warnings

**Detection Methods:**

1. **Standard Python script** (`inspect_stack`): Analyzes stack frames to find `run_algorithm()` caller
2. **Jupyter notebook** (`ipython`): Uses IPython metadata when available
3. **Frozen application** (`frozen`): Detects PyInstaller/cx_Freeze packaged apps
4. **Interactive REPL** (`fallback`): Best-effort detection for interactive sessions

**Example:**

```python
from rustybt.backtest.code_capture import StrategyCodeCapture

capturer = StrategyCodeCapture()

# Detect entry point
result = capturer.detect_entry_point()

if result.detected_file:
    print(f"✓ Entry point detected: {result.detected_file}")
    print(f"  Method: {result.detection_method}")
    print(f"  Confidence: {result.confidence}")

    if result.warnings:
        print(f"  Warnings: {len(result.warnings)}")
        for warning in result.warnings:
            print(f"    - {warning}")
else:
    print("✗ Entry point detection failed")
    print("  Create strategy.yaml to explicitly specify files")
    for warning in result.warnings:
        print(f"  - {warning}")
```

**Usage in different contexts:**

```python
# Standard script execution (best case)
# Running: python my_strategy.py
result = capturer.detect_entry_point()
# → detected_file: Path('my_strategy.py')
# → detection_method: 'inspect_stack'
# → confidence: 'high'

# Jupyter notebook
# Running from notebook cell
result = capturer.detect_entry_point()
# → detected_file: Path('Untitled.ipynb') or Path('<notebook>.ipynb')
# → detection_method: 'ipython'
# → confidence: 'medium'

# Frozen application (PyInstaller)
result = capturer.detect_entry_point()
# → detected_file: Path('my_strategy.py') (from bundled source)
# → detection_method: 'frozen'
# → confidence: 'medium'

# Interactive REPL (lowest confidence)
# Running: python -i
result = capturer.detect_entry_point()
# → detected_file: Path('<stdin>') or None
# → detection_method: 'fallback'
# → confidence: 'low'
# → warnings: ['Interactive session detected - use strategy.yaml for reliability']
```

---

## Methods

### `capture`

```python
def capture(
    self,
    strategy_yaml_path: str | Path | None = None
) -> list[str]
```

Execute code capture based on configured mode.

**Parameters:**

- **`strategy_yaml_path`** (`str | Path | None`, default: `None`)<br>
  Optional path to strategy.yaml. If provided, overrides auto-detection.

**Returns:** List of captured file paths (relative to output_dir)

**Raises:**

- **`FileNotFoundError`**: Required files not found
- **`ValueError`**: Invalid configuration
- **`OSError`**: Cannot copy files

**Example:**

```python
capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir='backtests/20251019_143527_123/code'
)

# Capture with auto-detected strategy.yaml
captured_files = capturer.capture()
print(captured_files)
# ['my_strategy.py', 'utils/indicators.py', 'utils/risk.py']

# Capture with explicit strategy.yaml path
captured_files = capturer.capture(strategy_yaml_path='custom_strategy.yaml')
```

---

### `analyze_imports`

```python
def analyze_imports(self) -> list[Path]
```

Analyze Python import statements to discover strategy files.

Uses Python's Abstract Syntax Tree (AST) to parse import statements and resolve module paths.

**Returns:** List of discovered file paths

**Raises:**

- **`SyntaxError`**: Invalid Python syntax in strategy file
- **`ImportError`**: Cannot resolve import paths

**Example:**

```python
capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir='output/code'
)

# Discover files via import analysis
files = capturer.analyze_imports()
print(files)
# [Path('my_strategy.py'), Path('utils/indicators.py'), Path('utils/risk.py')]
```

---

### `load_strategy_yaml`

```python
def load_strategy_yaml(
    self,
    yaml_path: str | Path | None = None
) -> list[Path]
```

Load file list from strategy.yaml configuration.

**Parameters:**

- **`yaml_path`** (`str | Path | None`, default: `None`)<br>
  Path to strategy.yaml. If `None`, looks in strategy directory.

**Returns:** List of file paths from YAML configuration

**Raises:**

- **`FileNotFoundError`**: strategy.yaml not found
- **`yaml.YAMLError`**: Invalid YAML format
- **`ValueError`**: Invalid YAML structure

**Example:**

```python
capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir='output/code',
    mode='strategy_yaml'
)

# Load from default location (same directory as strategy)
files = capturer.load_strategy_yaml()

# Load from custom location
files = capturer.load_strategy_yaml(yaml_path='config/strategy.yaml')

print(files)
# [Path('my_strategy.py'), Path('config/params.json'), Path('data/ref.csv')]
```

---

### `copy_files`

```python
def copy_files(
    self,
    files: list[Path]
) -> list[str]
```

Copy specified files to output directory, preserving structure.

**Parameters:**

- **`files`** (`list[Path]`)<br>
  List of file paths to copy

**Returns:** List of copied file paths (relative to output_dir)

**Raises:**

- **`FileNotFoundError`**: Source file not found (warns, doesn't fail)
- **`OSError`**: Cannot copy file (warns, doesn't fail)

**Example:**

```python
from pathlib import Path

capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir='output/code'
)

files_to_copy = [
    Path('my_strategy.py'),
    Path('utils/indicators.py'),
    Path('config/params.json')
]

copied = capturer.copy_files(files_to_copy)
print(copied)
# ['my_strategy.py', 'utils/indicators.py', 'config/params.json']

# Directory structure preserved:
# output/code/
#   ├── my_strategy.py
#   ├── utils/
#   │   └── indicators.py
#   └── config/
#       └── params.json
```

---

### `is_framework_module`

```python
@staticmethod
def is_framework_module(module_name: str) -> bool
```

Check if module is part of RustyBT framework.

**Parameters:**

- **`module_name`** (`str`)<br>
  Module name to check

**Returns:** `True` if framework module, `False` otherwise

**Example:**

```python
from rustybt.backtest import StrategyCodeCapture

# Framework modules
print(StrategyCodeCapture.is_framework_module('rustybt.algorithm'))  # True
print(StrategyCodeCapture.is_framework_module('rustybt.data'))       # True

# Non-framework modules
print(StrategyCodeCapture.is_framework_module('numpy'))              # False
print(StrategyCodeCapture.is_framework_module('my_strategy'))        # False
```

---

### `is_stdlib_module`

```python
@staticmethod
def is_stdlib_module(module_name: str) -> bool
```

Check if module is part of Python standard library.

**Parameters:**

- **`module_name`** (`str`)<br>
  Module name to check

**Returns:** `True` if stdlib module, `False` otherwise

**Example:**

```python
from rustybt.backtest import StrategyCodeCapture

# Standard library modules
print(StrategyCodeCapture.is_stdlib_module('os'))        # True
print(StrategyCodeCapture.is_stdlib_module('sys'))       # True
print(StrategyCodeCapture.is_stdlib_module('datetime'))  # True

# Non-stdlib modules
print(StrategyCodeCapture.is_stdlib_module('numpy'))     # False
print(StrategyCodeCapture.is_stdlib_module('pandas'))    # False
```

---

### `resolve_module_path`

```python
@staticmethod
def resolve_module_path(
    module_name: str,
    base_path: Path
) -> Path | None
```

Resolve module name to file system path.

**Parameters:**

- **`module_name`** (`str`)<br>
  Module name (e.g., `'utils.indicators'`)

- **`base_path`** (`Path`)<br>
  Base directory for resolution

**Returns:** Resolved file path or `None` if not found

**Example:**

```python
from pathlib import Path
from rustybt.backtest import StrategyCodeCapture

base = Path('/path/to/project')

# Resolve module to file
path = StrategyCodeCapture.resolve_module_path('utils.indicators', base)
print(path)  # Path('/path/to/project/utils/indicators.py')

# Module not found
path = StrategyCodeCapture.resolve_module_path('nonexistent', base)
print(path)  # None
```

## Usage Examples

### Example 1: Basic Import Analysis

```python
from rustybt.backtest import StrategyCodeCapture
from pathlib import Path

# Create capturer
capturer = StrategyCodeCapture(
    strategy_path='strategies/momentum.py',
    output_dir='backtests/20251019_143527_123/code'
)

# Capture strategy code
captured_files = capturer.capture()

print(f"Captured {len(captured_files)} files:")
for file in captured_files:
    print(f"  - {file}")

# Output:
# Captured 3 files:
#   - strategies/momentum.py
#   - indicators/technical.py
#   - risk/manager.py
```

### Example 2: Strategy YAML Configuration

**strategy.yaml:**
```yaml
files:
  - main_strategy.py
  - indicators/custom.py
  - config/params.json
  - data/reference.csv
```

**Python code:**
```python
from rustybt.backtest import StrategyCodeCapture

# Create capturer in YAML mode
capturer = StrategyCodeCapture(
    strategy_path='main_strategy.py',
    output_dir='backtests/20251019_143527_123/code',
    mode='strategy_yaml'
)

# Capture using strategy.yaml
captured_files = capturer.capture()

print("Captured files from strategy.yaml:")
for file in captured_files:
    print(f"  - {file}")

# Output:
# Captured files from strategy.yaml:
#   - main_strategy.py
#   - indicators/custom.py
#   - config/params.json
#   - data/reference.csv
```

### Example 3: Custom Import Analysis

```python
from rustybt.backtest import StrategyCodeCapture
from pathlib import Path

# Create capturer
capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir='output/code'
)

# Step 1: Analyze imports
discovered_files = capturer.analyze_imports()
print(f"Discovered {len(discovered_files)} files via import analysis")

# Step 2: Filter files (custom logic)
filtered_files = [
    f for f in discovered_files
    if not f.name.startswith('test_')
]

# Step 3: Copy filtered files
copied_files = capturer.copy_files(filtered_files)
print(f"Copied {len(copied_files)} files (excluded test files)")
```

### Example 4: Graceful Error Handling

```python
from rustybt.backtest import StrategyCodeCapture
import logging

# Enable logging to see warnings
logging.basicConfig(level=logging.WARNING)

capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir='output/code'
)

# Capture will warn about missing files but continue
captured_files = capturer.capture()

# Even if some files are missing, successful captures are returned
print(f"Successfully captured {len(captured_files)} files")

# Check what was captured
for file in captured_files:
    print(f"  ✓ {file}")
```

### Example 5: Integration with BacktestArtifactManager

```python
from rustybt.backtest import BacktestArtifactManager, StrategyCodeCapture

# Create artifact manager
manager = BacktestArtifactManager()
manager.initialize()

# Create code capturer
capturer = StrategyCodeCapture(
    strategy_path='my_strategy.py',
    output_dir=manager.code_dir
)

# Capture strategy code
captured_files = capturer.capture()

# Update metadata with captured files
metadata = {
    'backtest_id': manager.backtest_id,
    'captured_files': captured_files,
    'strategy_entry_point': str(Path('my_strategy.py').resolve())
}

manager.save_metadata(metadata)
print(f"Captured {len(captured_files)} files to {manager.code_dir}")
```

## Import Analysis Details

### Supported Import Patterns

The import analyzer supports these Python import patterns:

```python
# Absolute imports
import utils.indicators
from utils.indicators import calculate_rsi

# Relative imports
from . import indicators
from .utils import indicators
from ..shared import helpers

# Aliased imports
import utils.indicators as ind
from utils import indicators as ind

# Multiple imports
from utils.indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger
)
```

### Module Resolution

The analyzer resolves modules in this order:

1. **Relative to strategy directory** - Check for local modules
2. **Python path** - Use `sys.path` for resolution
3. **`importlib.util.find_spec()`** - Standard library resolution

### Filtering Logic

Modules are filtered to exclude:

- **Framework modules**: `rustybt.*`
- **Standard library**: `os`, `sys`, `datetime`, etc.
- **Third-party packages**: `numpy`, `pandas`, `ccxt`, etc.

Only local/user modules are captured.

## Strategy YAML Format

### Basic Format

```yaml
# Required: list of files to capture
files:
  - my_strategy.py
  - utils/indicators.py
  - config/params.json

# Optional: metadata (not used by system)
metadata:
  name: "My Strategy"
  version: "1.0.0"
  author: "Quant Team"
```

### Path Resolution

Paths in `strategy.yaml` are resolved relative to the YAML file location:

```yaml
# If strategy.yaml is in /project/strategies/
files:
  - main.py              # → /project/strategies/main.py
  - utils/helpers.py     # → /project/strategies/utils/helpers.py
  - ../config/params.py  # → /project/config/params.py
```

### Supported File Types

Any file type can be specified:

```yaml
files:
  # Python files
  - strategy.py
  - indicators.py

  # Configuration files
  - config.json
  - params.yaml
  - settings.toml

  # Data files
  - reference_data.csv
  - universe.parquet

  # Documentation
  - README.md
  - CHANGELOG.md
```

## Performance Considerations

### Import Analysis Performance

| Project Size | Files | Analysis Time |
|--------------|-------|---------------|
| Small | 1-5 | < 50ms |
| Medium | 10-20 | < 200ms |
| Large | 50+ | < 1s |
| Very Large | 200+ | < 3s |

### Optimization Tips

1. **Use strategy.yaml for large projects**
   ```yaml
   # Only capture necessary files
   files:
     - core_strategy.py
     - essential_utils.py
   ```

2. **Avoid deep import chains**
   ```python
   # Instead of:
   from utils.advanced.specialized.indicators import obscure_indicator

   # Use:
   from utils import obscure_indicator  # Flatten imports
   ```

3. **Cache analysis results** (if running multiple times)
   ```python
   # Analyze once
   files = capturer.analyze_imports()

   # Reuse results
   capturer.copy_files(files)
   ```

## Thread Safety

`StrategyCodeCapture` instances are **not thread-safe**. Create separate instances for concurrent operations:

```python
import threading
from rustybt.backtest import StrategyCodeCapture

def capture_strategy(strategy_path, output_dir):
    # Each thread gets its own instance
    capturer = StrategyCodeCapture(strategy_path, output_dir)
    return capturer.capture()

# Safe: separate instances per thread
threads = []
for i in range(5):
    t = threading.Thread(
        target=capture_strategy,
        args=(f'strategy_{i}.py', f'output_{i}/code')
    )
    threads.append(t)
    t.start()
```

## Error Handling

The code capturer uses graceful error handling:

- **Missing files**: Warns but continues
- **Permission errors**: Warns but continues
- **Invalid imports**: Logs warning and skips
- **Syntax errors**: Logs error and skips file

This ensures backtest execution continues even if code capture has issues.

**Example logging output:**
```
WARNING: Could not find imported module: advanced.experimental.indicators
WARNING: Permission denied copying: /restricted/secret_code.py
ERROR: Syntax error parsing: broken_strategy.py (backtest continues)
INFO: Successfully captured 8 of 10 discovered files
```

## See Also

- [Strategy Code Capture Guide](../../guides/strategy-code-capture.md)
- [Backtest Output Organization](../../guides/backtest-output-organization.md)
- [BacktestArtifactManager API](artifact-manager.md)
