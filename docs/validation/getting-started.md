# Getting Started with rustybt Validation Framework

This guide will help you run your first validation session in under 15 minutes.

## Prerequisites Checklist

Before you begin, verify you have the following installed:

### Python 3.12+

```bash
# Check Python version
python --version
# Expected: Python 3.12.x or higher

# If not 3.12+, install via pyenv or your package manager
# macOS: brew install python@3.12
# Ubuntu: sudo apt install python3.12
```

### Git

```bash
# Check git is installed
git --version
# Expected: git version 2.x.x
```

### pip or uv

```bash
# Check pip
pip --version
# or for faster installs, use uv
uv --version
```

## Installation

### Step 1: Clone the Repository

```bash
# Clone rustybt
git clone https://github.com/jerryinyang/rustybt.git
cd rustybt
```

### Step 2: Create Virtual Environment

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Unix/macOS
# or: .venv\Scripts\activate  # Windows
```

### Step 3: Install with Validation Dependencies

```bash
# Install rustybt with validation extras (includes Backtrader)
pip install -e ".[validation]"
```

This installs:
- rustybt core framework
- Backtrader reference implementation
- Polars for log comparison
- Click for CLI interface
- pytest for testing

### Step 4: Verify Installation

```bash
# Check CLI is available
rustybt-validate --version
# Expected: rustybt-validate, version 0.x.x

# Verify imports work
python -c "from rustybt.validation import SessionManager; print('OK')"
# Expected: OK

# Verify Backtrader is installed
python -c "import backtrader; print('Backtrader:', backtrader.__version__)"
# Expected: Backtrader: 1.9.78.x
```

## Quick Start: Your First Validation Session

### Step 1: Generate Test Data Fixture

First, create sample OHLCV data for validation:

```bash
rustybt-validate generate-fixture \
    tests/validation/fixtures/validation_data.parquet \
    --assets 10 \
    --seed 42
```

Expected output:
```
Generating fixture with 10 assets...
Saving to tests/validation/fixtures/validation_data.parquet
Generated 10 assets with 252 days of data each
Fixture saved successfully!
```

### Step 2: Create Validation Session

Create a session for the SMA Crossover strategy:

```bash
rustybt-validate session create \
    --strategy sma_crossover \
    --data tests/validation/fixtures/validation_data.parquet
```

Expected output:
```
Creating validation session...
Session ID: 20251129-120000-sma_crossover
Status: IN_PROGRESS
Strategy: sma_crossover
Data: tests/validation/fixtures/validation_data.parquet

Session created successfully!
Use 'rustybt-validate run 20251129-120000-sma_crossover' to execute validation.
```

### Step 3: Run Validation

Execute the validation to compare rustybt vs Backtrader:

```bash
rustybt-validate run <session_id>
```

Expected output:
```
Running validation for session: 20251129-120000-sma_crossover

Executing rustybt strategy...
[========================================] 100%
Logs written to: validation-sessions/20251129-120000-sma_crossover/rustybt.jsonl

Executing Backtrader strategy...
[========================================] 100%
Logs written to: validation-sessions/20251129-120000-sma_crossover/backtrader.jsonl

Comparing logs across 5 layers...
Layer 1 (Data): 0 discrepancies
Layer 2 (Signals): 0 discrepancies
Layer 3 (Orders): 0 discrepancies
Layer 4 (Broker): 0 discrepancies
Layer 5 (Portfolio): 0 discrepancies

Validation complete! No discrepancies found.
```

### Step 4: View Results

Generate a validation report:

```bash
rustybt-validate report <session_id>
```

Expected output:
```
# Validation Report: 20251129-120000-sma_crossover

## Summary
- Strategy: sma_crossover
- Status: VALIDATED
- Total Findings: 0 discrepancies

## Layer Results
| Layer    | Status  | Discrepancies |
|----------|---------|---------------|
| Data     | PASS    | 0             |
| Signals  | PASS    | 0             |
| Orders   | PASS    | 0             |
| Broker   | PASS    | 0             |
| Portfolio| PASS    | 0             |

## Conclusion
The SMA Crossover strategy produces identical results in both frameworks.
```

## Managing Sessions

### List All Sessions

```bash
rustybt-validate session list
```

### View Session Details

```bash
rustybt-validate session show <session_id>
```

### View Validation Progress

```bash
rustybt-validate progress
```

### Check Overall Status

```bash
rustybt-validate status
```

## Python API

For programmatic access, use the Python API:

```python
from pathlib import Path
from rustybt.validation.session import SessionManager
from rustybt.validation.models import Finding

# Create session manager
sm = SessionManager()

# Create new session
session = sm.create_session(
    strategy_name="sma_crossover",
    data_fixture=Path("tests/validation/fixtures/validation_data.parquet"),
    rustybt_version="0.3.4",
    backtrader_version="1.9.78",
)
print(f"Created session: {session.id}")

# List existing sessions
for s in sm.list_sessions():
    print(f"{s.id}: {s.status}")

# Load and update session
session = sm.load_session("20251129-120000-sma_crossover")
session.notes = "Initial validation run"
sm.update_session(session)
```

## Troubleshooting

### ModuleNotFoundError: No module named 'backtrader'

**Cause:** Validation dependencies not installed.

**Solution:**
```bash
pip install -e ".[validation]"
```

### PermissionError: validation-sessions/

**Cause:** Directory permissions issue.

**Solution:**
```bash
mkdir -p validation-sessions
chmod 755 validation-sessions/
```

### FileNotFoundError: validation_data.parquet

**Cause:** Test fixture not generated.

**Solution:**
```bash
rustybt-validate generate-fixture tests/validation/fixtures/validation_data.parquet
```

### Version conflicts between packages

**Cause:** Conflicting package versions in environment.

**Solution:**
```bash
# Create fresh virtual environment
python -m venv .venv-clean
source .venv-clean/bin/activate
pip install -e ".[validation]"
```

### Session already exists error

**Cause:** Trying to create duplicate session.

**Solution:**
```bash
# Use --force to supersede existing session
rustybt-validate session create \
    --strategy sma_crossover \
    --data tests/validation/fixtures/validation_data.parquet \
    --force
```

### Subprocess timeout during execution

**Cause:** Strategy taking too long to execute.

**Solution:**
```bash
# Reduce data size
rustybt-validate generate-fixture \
    tests/validation/fixtures/validation_data_small.parquet \
    --assets 3 \
    --days 60
```

## Next Steps

Now that you've run your first validation, explore these guides:

- **[Strategy Implementation Guide](strategy-implementation-guide.md)** - Add your own strategies to the validation suite
- **[Investigation Workflow Guide](investigation-guide.md)** - Learn how to investigate and classify discrepancies
- **[Design Differences](design-differences.md)** - Understand known differences between rustybt and Backtrader
- **[Validation Summary](validation-summary.md)** - View current validation status across all strategies

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/jerryinyang/rustybt/issues)
- **Discussions:** [GitHub Discussions](https://github.com/jerryinyang/rustybt/discussions)
- **CLI Help:** `rustybt-validate --help`
