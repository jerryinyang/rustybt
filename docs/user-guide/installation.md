# Installation Guide

## Quick Start

### Basic Installation

Install RustyBT with core dependencies only:

```bash
pip install rustybt
```

This installs the essential packages needed for basic backtesting functionality.

### Full Installation (Recommended)

**New in v1.x**: Install all optional features with a single command:

```bash
pip install rustybt[full]
```

Or equivalently:

```bash
pip install rustybt[all]
```

This installs:
- **Optimization tools**: scikit-learn, scikit-optimize, DEAP for parameter optimization
- **Performance benchmarking**: pytest-benchmark, memory_profiler for profiling
- **Visualization**: matplotlib for charts and analysis

**Installation time**: ~3-5 minutes on standard internet connections
**Total size**: ~500 MB (including all dependencies)

## Installation Options

### Granular Installation (Advanced)

For more control, install specific feature groups:

```bash
# Optimization tools only
pip install rustybt[optimization]

# Benchmarking tools only
pip install rustybt[benchmarks]

# Development tools (for contributors)
pip install rustybt[dev]

# Testing tools (for contributors)
pip install rustybt[test]

# Documentation tools (for contributors)
pip install rustybt[docs]
```

### Combining Multiple Extras

You can combine multiple extras:

```bash
pip install rustybt[optimization,benchmarks]
```

**However**, using `[full]` is simpler and guaranteed to include all user-facing features.

## What's Included

### Core Dependencies (Always Installed)

- **Data processing**: Polars, PyArrow, Pandas
- **Financial calculations**: NumPy, SciPy, statsmodels
- **Data sources**: CCXT (crypto exchanges), yfinance (stocks)
- **Live trading**: ib-insync (Interactive Brokers), pybit (Bybit), Hyperliquid SDK
- **Visualization**: Plotly, Seaborn, ipywidgets
- **Type safety**: Pydantic, structlog

### Full/All Extras (Optional Features)

The `[full]` and `[all]` extras include:

#### Optimization Tools (`[optimization]`)
- **scikit-learn** (≥1.3.0): Machine learning, sensitivity analysis, bootstrap resampling
- **scikit-optimize** (≥0.9.0): Bayesian optimization for parameter tuning
- **DEAP** (≥1.4.0): Genetic algorithms for evolutionary optimization
- **matplotlib** (≥3.5.0): Plotting and visualization
- **tqdm** (≥4.0.0): Progress bars for long-running optimizations
- **psutil** (≥5.0.0): System resource monitoring

#### Benchmarking Tools (`[benchmarks]`)
- **pytest-benchmark** (≥3.4.1): Performance benchmarking framework
- **memory_profiler** (≥0.61.0): Memory usage profiling
- **snakeviz** (≥2.2.0): Profiling visualization
- **matplotlib** (≥3.5.0): Plotting benchmark results

**Total packages**: ~9-12 packages (depending on existing dependencies)

### Development Extras (For Contributors Only)

The `[dev]`, `[test]`, and `[docs]` extras are **NOT included in [full]**. These are intended for framework contributors only:

- `[dev]`: Linters (ruff, black, mypy), type stubs, Jupyter tools
- `[test]`: Testing framework (pytest, tox, hypothesis, coverage)
- `[docs]`: Documentation generation (Sphinx, MkDocs)

**Why separate?** End users don't need development tools, and including them would significantly increase installation size (~1.5 GB total).

## Python Version Requirements

**Minimum**: Python 3.12+

**Recommended**: Python 3.12 or 3.13

RustyBT requires modern Python features (structural pattern matching, enhanced type hints) introduced in Python 3.12.

## Upgrading from Previous Versions

### Upgrading to Latest Version

```bash
pip install --upgrade rustybt[full]
```

### Upgrading from Minimal to Full Installation

If you previously installed RustyBT without extras:

```bash
# Upgrade and add all optional features
pip install --upgrade rustybt[full]
```

This adds missing dependencies without reinstalling core packages.

### Checking Installed Version

```bash
pip show rustybt
```

Or within Python:

```python
import rustybt
print(rustybt.__version__)
```

## Verifying Installation

### Quick Verification

Test that all core features are available:

```python
import rustybt
from rustybt import run_algorithm
from rustybt.api import symbol, order_target_percent
import polars as pl
import ccxt

print("✓ RustyBT core installation verified")
```

### Verifying Full Installation

Check that optional features are available:

```python
# Optimization tools
import sklearn
import skopt
import deap

# Benchmarking tools
import pytest_benchmark
import memory_profiler
import snakeviz

print("✓ RustyBT full installation verified")
```

## Common Installation Issues

### ImportError for Optional Features

**Symptom**: `ImportError: No module named 'sklearn'` or similar.

**Solution**: Install the full extras:
```bash
pip install rustybt[full]
```

### Conflicting Dependencies

**Symptom**: Pip resolver errors about incompatible package versions.

**Solution**:
1. Create a fresh virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install rustybt[full]
   ```

2. Or upgrade pip first:
   ```bash
   pip install --upgrade pip
   pip install rustybt[full]
   ```

### Slow Installation

**Symptom**: Installation takes >10 minutes or appears stuck.

**Possible causes**:
- Slow internet connection
- Building packages from source (NumPy, Cython components)

**Solution**:
1. Ensure pip is updated: `pip install --upgrade pip`
2. Use binary wheels if available: `pip install --only-binary=:all: rustybt[full]` (may fail for some packages)
3. Be patient — first installation compiles Cython extensions

### NumPy Compatibility Issues

**Symptom**: Errors related to NumPy version conflicts.

**Solution**: RustyBT automatically selects the correct NumPy version:
- Python 3.12: NumPy <2.0
- Python 3.13+: NumPy ≥2.1

If issues persist, create a fresh virtual environment.

### SSL Certificate Errors

**Symptom**: `SSL: CERTIFICATE_VERIFY_FAILED` during installation.

**Solution** (macOS):
```bash
/Applications/Python\ 3.12/Install\ Certificates.command
```

**Solution** (general):
```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org rustybt[full]
```

## Virtual Environment Setup (Recommended)

### Why Use Virtual Environments?

Virtual environments isolate RustyBT and its dependencies from system Python, preventing version conflicts.

### Creating a Virtual Environment

#### Using venv (built-in)

```bash
# Create virtual environment
python -m venv rustybt-env

# Activate (Linux/macOS)
source rustybt-env/bin/activate

# Activate (Windows)
rustybt-env\Scripts\activate

# Install RustyBT
pip install rustybt[full]
```

#### Using conda

```bash
# Create conda environment with Python 3.12
conda create -n rustybt python=3.12

# Activate
conda activate rustybt

# Install RustyBT
pip install rustybt[full]
```

### Deactivating Virtual Environment

```bash
deactivate  # venv
conda deactivate  # conda
```

## Platform-Specific Notes

### macOS

**Requirements**:
- Xcode Command Line Tools (for Cython compilation):
  ```bash
  xcode-select --install
  ```

**Apple Silicon (M1/M2/M3)**: All dependencies have native ARM64 wheels. Installation is fully supported.

### Linux

**Requirements**:
- Build tools:
  ```bash
  # Debian/Ubuntu
  sudo apt-get install build-essential python3-dev

  # Fedora/RHEL
  sudo dnf install gcc gcc-c++ python3-devel
  ```

### Windows

**Requirements**:
- Microsoft Visual C++ Build Tools (for Cython compilation)
- Download from: https://visualstudio.microsoft.com/downloads/

**Windows Subsystem for Linux (WSL)**: Fully supported, follow Linux instructions.

## Docker Installation (Advanced)

For containerized deployments:

```dockerfile
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install RustyBT
RUN pip install --no-cache-dir rustybt[full]

# Set working directory
WORKDIR /app

# Copy strategy files
COPY . /app

# Run strategy
CMD ["python", "my_strategy.py"]
```

Build and run:
```bash
docker build -t rustybt-strategy .
docker run rustybt-strategy
```

## Uninstalling

### Removing RustyBT

```bash
pip uninstall rustybt
```

### Removing All Dependencies

To remove RustyBT and all dependencies it installed:

```bash
# List dependencies
pip show rustybt

# Uninstall RustyBT and dependencies
pip uninstall rustybt -y
pip uninstall <dependency1> <dependency2> ... -y
```

**Easier approach**: Delete the virtual environment and start fresh if needed.

## Next Steps

After installation:

1. **Run a simple backtest**: [Quickstart Tutorial](../quickstart.md)
2. **Understand code capture**: [Code Capture Guide](code-capture.md)
3. **Optimize strategies**: [Optimization Guide](../optimization/README.md)
4. **Go live**: [Live Trading Setup](../live-trading/setup.md)

## Getting Help

**Installation issues**: https://github.com/jerryinyang/rustybt/issues
**Documentation**: https://jerryinyang.github.io/rustybt/
**Discussions**: https://github.com/jerryinyang/rustybt/discussions
