# Strategy Code Capture

## Overview

RustyBT automatically captures your strategy code during backtest runs to ensure reproducibility and enable audit trails. This feature stores a snapshot of your strategy source code alongside backtest results, allowing you to recreate exact execution conditions later.

**New in v1.x**: The default behavior has changed to optimize storage efficiency during optimization runs.

## Default Behavior (Entry Point Only)

**By default, RustyBT now stores only the entry point file** — the file containing your `run_algorithm()` call. This dramatically reduces storage consumption during optimization operations that may run hundreds or thousands of backtests.

### Example: Single File Strategy

```python
# my_strategy.py
from rustybt import run_algorithm
from rustybt.api import order_target_percent, symbol

def initialize(context):
    """Initialize strategy state."""
    context.asset = symbol('AAPL')
    context.rebalance_frequency = 10

def handle_data(context, data):
    """Execute trading logic."""
    if context.rebalance_frequency % 10 == 0:
        order_target_percent(context.asset, 0.5)

# Entry point - only this file will be stored
run_algorithm(
    start='2020-01-01',
    end='2020-12-31',
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000,
)
```

**Storage behavior**: Only `my_strategy.py` is captured and stored in the backtest output directory.

### Storage Comparison

| Scenario | Old Behavior (Import Analysis) | New Behavior (Entry Point Only) | Storage Reduction |
|----------|-------------------------------|----------------------------------|-------------------|
| Single backtest | ~10 KB (main file + imports) | ~2 KB (main file only) | ~80% |
| 10-iteration optimization | ~100 KB (10x all imports) | ~20 KB (10x main file) | ~80% |
| 100-iteration optimization | ~1 MB (100x all imports) | ~200 KB (100x main file) | **~80-95%** |

**Real-world impact**: For a 100-iteration optimization, storage reduces from ~1 MB to ~200 KB, enabling larger-scale optimization studies without storage concerns.

## YAML Configuration Override

**For multi-file strategies**, you can explicitly specify which files to capture using a YAML configuration file. This gives you full control over what gets stored.

### Creating a YAML Configuration

Create a `strategy.yaml` file in your project:

```yaml
# strategy.yaml
files:
  - my_strategy.py
  - utils/indicators.py
  - utils/risk_management.py
  - config/parameters.json
```

**Supported file types**: Python files (`.py`), JSON config files (`.json`), YAML files (`.yaml`), and any other text-based configuration.

### Example: Multi-File Strategy with YAML

```
my_project/
├── strategy.yaml          # Explicitly lists files to capture
├── my_strategy.py         # Entry point
├── utils/
│   ├── indicators.py      # Custom indicators
│   └── risk_management.py # Risk rules
└── config/
    └── parameters.json    # Strategy parameters
```

**YAML configuration (strategy.yaml)**:
```yaml
files:
  - my_strategy.py
  - utils/indicators.py
  - utils/risk_management.py
  - config/parameters.json
```

**Storage behavior**: All files listed in `strategy.yaml` are captured, **regardless of import analysis**. The entry point file is automatically included even if not listed.

### YAML Precedence

**YAML configuration takes precedence** over entry point detection:

1. **YAML exists**: Use files listed in `strategy.yaml` (ignores entry point detection)
2. **No YAML**: Use entry point detection (stores only the file with `run_algorithm()` call)

## Entry Point Detection

RustyBT uses runtime introspection to identify the file containing the `run_algorithm()` call. This works reliably in most scenarios:

### Supported Execution Contexts

| Context | Detection Method | Confidence | Notes |
|---------|-----------------|------------|-------|
| **Standard Python script** | `inspect.stack()` | 100% | Most common scenario |
| **Jupyter notebook** | IPython metadata + fallback | 70-80% | May prompt for confirmation |
| **Interactive session** | Stack analysis | 50-70% | Best effort; YAML recommended |
| **Frozen application** | PyInstaller detection | 80% | Works for most packaged apps |

### Edge Cases

**Jupyter Notebooks**: Entry point detection works but may not always identify the exact notebook file. Use YAML configuration for guaranteed accuracy.

**Interactive REPL**: Detection is best-effort. For production workflows, use a script file or YAML configuration.

**Dynamic imports**: If `run_algorithm()` is called from dynamically loaded code, detection may fail. Use YAML configuration.

### Detection Warnings

If entry point detection encounters issues, you'll see warnings in the log output:

```
WARNING - Entry point detection: Could not reliably identify entry point file
INFO - Falling back to YAML configuration or skipping code capture
```

**Resolution**: Create a `strategy.yaml` file to explicitly specify files.

## Troubleshooting

### Entry Point Not Detected

**Symptom**: Warning message about failed entry point detection, or no code files stored.

**Solution**:
1. Create `strategy.yaml` with explicit file list
2. Ensure `run_algorithm()` is called directly in your script (not nested in functions)
3. Verify you're running a standard Python script (not interactive session)

### YAML Files Not Found

**Symptom**: Warning message about missing files listed in `strategy.yaml`.

**Solution**:
1. Verify file paths in `strategy.yaml` are relative to the YAML file location
2. Check file permissions (files must be readable)
3. Ensure file paths use forward slashes (`/`) even on Windows

### Storage Growing Exponentially

**Symptom**: Backtest storage directory growing much larger than expected during optimization.

**Solution**:
1. **Remove YAML configuration** to use new default (entry point only)
2. If you need multi-file capture, ensure YAML lists only essential files
3. Avoid wildcards or directory patterns in YAML (list files explicitly)

## Migration Guide (Upgrading from Previous Versions)

### Behavior Change

**Old behavior (v0.x)**: Automatic import analysis stored all imported local modules recursively.

**New behavior (v1.x)**: Entry point detection stores only the main file by default.

### Backward Compatibility

**Existing YAML configurations are 100% backward compatible**. If you have `strategy.yaml` files, they continue to work exactly as before.

### Migration Recommendations

**Single-file strategies**: No changes needed. New behavior is more efficient.

**Multi-file strategies**:
- **Option 1**: Create `strategy.yaml` to explicitly list required files (recommended for reproducibility)
- **Option 2**: Consolidate code into a single file if possible (simplest approach)
- **Option 3**: Accept new behavior and only the entry point is stored (if imports aren't critical for reproduction)

## Performance Impact

**Entry point detection overhead**: < 10ms per backtest run (negligible impact)

**Storage I/O impact**: ~80-95% reduction in file copy operations during optimization

**Execution performance**: No measurable impact on backtest execution time (within 2% variance)

## API Reference

For advanced use cases, you can access code capture programmatically:

```python
from rustybt.backtest.code_capture import StrategyCodeCapture

# Manually trigger code capture
capturer = StrategyCodeCapture()
result = capturer.detect_entry_point()

if result.detected_file:
    print(f"Entry point: {result.detected_file}")
    print(f"Detection method: {result.detection_method}")
    print(f"Confidence: {result.confidence}")
else:
    print("Entry point detection failed")
```

## Best Practices

1. **For single-file strategies**: Use default behavior (no YAML needed)
2. **For multi-file strategies**: Create explicit `strategy.yaml` for clarity
3. **For optimization runs**: Minimize captured files to reduce storage (default behavior handles this)
4. **For production backtests**: Use YAML to guarantee reproducibility
5. **Always test in single backtest** before running large optimization studies

## Related Documentation

- [Optimization Storage Guide](optimization-storage.md) - Storage optimization during parameter sweeps
- [Installation Guide](installation.md) - Installing RustyBT with full features
- [Backtest Configuration](backtest-configuration.md) - Configuring backtest runs
