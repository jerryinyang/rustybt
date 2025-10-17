# Installation Guide

## Prerequisites

- Python 3.12 or higher
- pip (included with Python)
- Git (only for development installation from source)

## From PyPI (Recommended)

The easiest way to install RustyBT is from PyPI:

### Basic Installation

```bash
pip install rustybt
```

This installs the core package with minimal dependencies suitable for production use.

### Installation with Optional Features

```bash
# Strategy optimization tools (scikit-learn, genetic algorithms)
pip install rustybt[optimization]

# Development tools (jupyter, jupyterlab, ruff, mypy, black)
pip install rustybt[dev]

# Testing tools (pytest, hypothesis, coverage)
pip install rustybt[test]

# Multiple extras
pip install rustybt[optimization,dev,test]
```

### Available Extras

- `optimization` - Strategy optimization (scikit-learn, genetic algorithms, walk-forward)
- `dev` - Development tools (jupyter, jupyterlab, ruff, mypy, black, type stubs)
- `test` - Testing tools (pytest, hypothesis, coverage)
- `benchmarks` - Performance profiling tools (cProfile, memory-profiler)
- `docs` - Documentation generation (MkDocs with Material theme)

### Using a Virtual Environment (Recommended)

It's recommended to install RustyBT in a virtual environment:

```bash
# Create virtual environment
python3.12 -m venv rustybt-env

# Activate virtual environment
# On Unix/macOS:
source rustybt-env/bin/activate

# On Windows:
rustybt-env\Scripts\activate

# Install RustyBT
pip install rustybt[optimization]
```

## From Source (Development)

For contributors or those who want the latest development version:

### Clone the Repository

```bash
git clone https://github.com/jerryinyang/rustybt.git
cd rustybt
```

### Using uv (Recommended for Development)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer:

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install with specific extras
uv sync --extra dev --extra test

# Or install all optional extras
uv sync --all-extras
```

### Using pip

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Unix/macOS
# or .venv\Scripts\activate on Windows

# Install in editable mode with dev tools
pip install -e ".[dev,test]"
```

## Verification

Verify your installation:

```bash
# Check RustyBT version and import
python -c "import rustybt; print(rustybt.__version__)"

# Verify CLI is available
rustybt --help
```

## Next Steps

- [Quick Start Tutorial](quickstart.md) - Write your first trading strategy
- [Configuration](configuration.md) - Configure RustyBT for your needs
- [User Guides](../guides/decimal-precision-configuration.md) - Explore features
