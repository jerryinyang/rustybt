# Strategy YAML Code Capture

This directory contains example `strategy.yaml` files demonstrating how to use explicit code capture for your backtesting strategies.

## Overview

By default, RustyBT uses **automatic import analysis** to capture your strategy code. However, for complex projects, you can use a `strategy.yaml` file to **explicitly specify** which files should be captured.

## Quick Start

1. Create a `strategy.yaml` file in the same directory as your strategy entry point
2. List the files you want to capture (relative paths)
3. Run your backtest normally

```yaml
# strategy.yaml
files:
  - my_strategy.py
  - utils/indicators.py
  - config/settings.json
```

## When to Use strategy.yaml

### ✅ Use strategy.yaml when:
- You have **dynamically loaded modules** that import analysis misses
- You need to include **non-Python files** (JSON configs, YAML params, CSVs)
- You want to capture **documentation** (README.md, CHANGELOG.md)
- You have **complex import patterns** that don't follow standard conventions
- You need **precise control** over what gets captured

### ❌ Don't use strategy.yaml when:
- Your strategy uses simple, straightforward imports
- All dependencies are standard Python modules with clear import statements
- You're okay with automatic import detection

## Precedence Rules

The system uses this decision tree:

1. **IF** `strategy.yaml` exists → **Use YAML** (explicit file always wins)
2. **ELSE IF** `code_capture_mode: "strategy_yaml"` → **Warn and fall back** to import analysis
3. **ELSE** → **Use import analysis** (default)

**Key Principle:** Presence of `strategy.yaml` = explicit user intent, always honored.

## Example Use Cases

### Example 1: Including Configuration Files

```yaml
# strategy.yaml
files:
  - momentum_strategy.py
  - config/backtest_params.json  # JSON config
  - config/risk_limits.yaml       # YAML params
```

### Example 2: Multi-Module Strategy

```yaml
# strategy.yaml
files:
  - strategy.py
  - indicators/technical.py
  - indicators/fundamental.py
  - risk/position_sizing.py
  - risk/stop_loss.py
  - utils/data_loader.py
  - utils/logging.py
```

### Example 3: Including Documentation

```yaml
# strategy.yaml
files:
  - my_strategy.py
  - README.md           # Strategy documentation
  - CHANGELOG.md        # Version history
  - PERFORMANCE.md      # Performance notes
```

### Example 4: Data Files and References

```yaml
# strategy.yaml
files:
  - strategy.py
  - data/sector_weights.csv       # Reference data
  - data/benchmark_returns.parquet
  - notebooks/analysis.ipynb      # Jupyter notebook
```

## Configuration

You can set the default code capture mode in your backtest configuration:

```yaml
# backtest_config.yaml
backtest_output:
  enabled: true
  base_dir: "backtests"
  code_capture_mode: "import_analysis"  # or "strategy_yaml"
```

However, **if `strategy.yaml` exists, it ALWAYS takes precedence** regardless of this setting.

## File Structure Preservation

Directory structure is **automatically preserved**:

**Input:**
```
my_strategy/
├── strategy.py
├── strategy.yaml
└── utils/
    └── deep/
        └── nested/
            └── module.py
```

**YAML:**
```yaml
files:
  - strategy.py
  - utils/deep/nested/module.py
```

**Output in backtest directory:**
```
backtests/20251018_143527_123/code/
├── strategy.py
└── utils/
    └── deep/
        └── nested/
            └── module.py
```

## Error Handling

The system is **robust to errors**:

- **Missing file listed in YAML:** Logs warning, continues with other files
- **Malformed YAML:** Logs error, falls back to import analysis
- **Empty files list:** Valid, captures only explicitly listed files (if any)
- **File copy error:** Logs warning, continues with remaining files

**The backtest always proceeds**, even if YAML processing encounters issues.

## Logging

The system logs its decisions clearly:

```
INFO: Using strategy.yaml for code capture (explicit file found)
INFO: Captured 5 files from strategy.yaml
```

Or:

```
INFO: Using import analysis (no strategy.yaml found)
```

## Performance

YAML-based capture is **typically faster** than import analysis:
- No AST parsing overhead
- Simple file list iteration
- Completes in <5 seconds for typical projects (per spec)

Benchmark: 50-file capture completed in ~0.02 seconds.

## Best Practices

1. **Keep it minimal:** Only list files you actually need
2. **Use relative paths:** All paths relative to strategy directory
3. **Include configs:** Don't forget non-Python configuration files
4. **Add comments:** Document why specific files are included
5. **Version control:** Commit `strategy.yaml` with your strategy code

## Troubleshooting

**Q: My YAML file isn't being used**
A: Ensure `strategy.yaml` is in the same directory as your strategy entry point.

**Q: File not found warning**
A: Check the relative path is correct from the strategy directory.

**Q: YAML parse error**
A: Validate your YAML syntax. Use a YAML validator online.

**Q: Want to go back to import analysis**
A: Simply delete or rename `strategy.yaml`.

## See Also

- [Backtest Output Organization](../../guides/backtest-output.md)
- [Import Analysis](../../guides/import-analysis.md)
- [Configuration Reference](../../reference/configuration.md)
