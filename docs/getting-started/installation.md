# Installation Guide

## Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git (for development installation)

## Using uv (Recommended)

### Production Installation

For minimal dependencies suitable for production use:

```bash
uv sync
```

### Development Installation

For development with dev tools, notebooks, and tests:

```bash
# Install with specific extras
uv sync --extra dev --extra test

# Or install all optional extras
uv sync --all-extras
```

### Available Extras

- `dev` - Development tools (jupyter, jupyterlab, ruff, mypy, black, type stubs)
- `test` - Testing tools (pytest, hypothesis, coverage)
- `benchmarks` - Performance profiling tools
- `optimization` - Strategy optimization (scikit-learn, genetic algorithms)
- `docs` - Documentation generation (MkDocs, Material theme)

## Using pip

### Create Virtual Environment

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate virtual environment
# On Unix/macOS:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### Install RustyBT

```bash
# Development installation
pip install -e ".[dev,test]"

# Or production installation (minimal dependencies)
pip install -e .
```

## Verification

Verify your installation:

```bash
# Check RustyBT version
rustybt --version

# Run a quick test
python -c "import rustybt; print(rustybt.__version__)"
```

## Next Steps

- [Quick Start Tutorial](quickstart.md) - Write your first trading strategy
- [Configuration](configuration.md) - Configure RustyBT for your needs
- [User Guides](../guides/decimal-precision-configuration.md) - Explore features
