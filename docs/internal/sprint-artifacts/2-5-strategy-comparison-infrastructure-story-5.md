# Story 2.5: Create Strategy Execution Wrapper Scripts

Status: done

## Story

As a developer,
I want CLI wrapper scripts for each framework,
so that subprocess runners can execute strategies with consistent interfaces.

## Acceptance Criteria

1. **execute_rustybt.py CLI wrapper implemented** - `rustybt/validation/execute_rustybt.py`:
   - CLI arguments: --strategy, --data, --output, --params (optional)
   - Imports strategy class from module path
   - Loads data from Parquet
   - Executes strategy with logging
   - Exit code 0 on success, 1 on failure

2. **execute_backtrader.py CLI wrapper implemented** - `rustybt/validation/execute_backtrader.py`:
   - Same CLI arguments as rustybt wrapper
   - Creates Cerebro engine
   - Loads data into Backtrader feed
   - Adds strategy with params
   - Runs and exits appropriately

3. **Both scripts validate inputs**:
   - Check strategy module exists and is importable
   - Check data file exists
   - Check output directory exists or create it
   - Validate params JSON if provided

4. **Both scripts use identical parameter names**:
   - --strategy for module path
   - --data for data fixture path
   - --output for log output path
   - --params for JSON parameters

5. **Error handling provides clear messages**:
   - Import errors: "Could not import strategy: <module>"
   - Data errors: "Data file not found: <path>"
   - Execution errors: Full traceback to stderr

6. **Unit tests verify CLI argument parsing**:
   - Test valid arguments
   - Test missing required arguments
   - Test invalid JSON params

## Tasks / Subtasks

- [x] Task 1: Create execute_rustybt.py script (AC: #1, #3, #4, #5)
  - [x] Create `rustybt/validation/execute_rustybt.py`
  - [x] Import argparse, json, Path, importlib
  - [x] Define main() function with argument parsing
  - [x] Implement import_strategy() helper
  - [x] Implement load_data() helper
  - [x] Execute strategy with log_path parameter
  - [x] Add proper exit codes

- [x] Task 2: Create execute_backtrader.py script (AC: #2, #3, #4, #5)
  - [x] Create `rustybt/validation/execute_backtrader.py`
  - [x] Import argparse, json, Path, importlib, backtrader
  - [x] Define main() function with identical argument parsing
  - [x] Create Cerebro engine
  - [x] Load Parquet data into Backtrader feed
  - [x] Add strategy with params
  - [x] Run and exit appropriately

- [x] Task 3: Implement shared utilities
  - [x] Create import_strategy() that works for both frameworks
  - [x] Handle dotted module paths (e.g., "tests.validation.strategies.rustybt.sma")
  - [x] Return strategy class from module

- [x] Task 4: Implement input validation (AC: #3)
  - [x] Check data file exists before loading
  - [x] Check output directory exists or create
  - [x] Validate JSON params format
  - [x] Exit with code 1 on validation failure

- [x] Task 5: Write unit tests (AC: #6)
  - [x] Create `tests/validation/test_execute_scripts.py`
  - [x] Test argument parsing for both scripts
  - [x] Test missing required arguments
  - [x] Test invalid JSON params
  - [x] Test strategy import errors

## Dev Notes

### Learnings from Previous Story

**From Story 2-4 (Status: drafted)**

- **Runner Functions Created**: `run_rustybt_strategy()`, `run_backtrader_strategy()` in `rustybt/validation/runner.py`
- **Subprocess Execution**: Runners call these wrapper scripts via subprocess
- **CLI Arguments**: --strategy, --data, --output, --params passed from runners

**Wrapper scripts are targets of runner functions** (from Story 2.4):
- Runners use sys.executable -m rustybt.validation.execute_rustybt
- Runners use sys.executable -m rustybt.validation.execute_backtrader
- Both must accept identical CLI arguments

[Source: docs/sprint-artifacts/2-4-strategy-comparison-infrastructure-story-4.md]

### Architecture Alignment

**CLI Wrapper Pattern** (Architecture pg 249-268):
- Separate execution scripts for isolation
- Same Python interpreter via sys.executable
- Consistent argument interface

**Data Loading**:
- rustybt: Use existing data loading utilities
- Backtrader: May need adapter (Parquet → bt.feeds)

### Implementation Pattern

**execute_rustybt.py**:
```python
"""CLI wrapper for rustybt strategy execution."""
import argparse
import importlib
import json
import sys
from pathlib import Path


def import_strategy(module_path: str):
    """Import strategy class from dotted module path.

    Args:
        module_path: e.g., "tests.validation.strategies.rustybt.sma_crossover.SMAStrategy"

    Returns:
        Strategy class
    """
    parts = module_path.rsplit(".", 1)
    if len(parts) == 2:
        module_name, class_name = parts
    else:
        module_name = parts[0]
        class_name = "Strategy"  # Default class name

    try:
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        print(f"Could not import strategy: {module_path}", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def load_data(data_path: Path):
    """Load data from Parquet file."""
    if not data_path.exists():
        print(f"Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    # Use rustybt's data loading utilities
    import polars as pl
    return pl.read_parquet(data_path)


def main():
    parser = argparse.ArgumentParser(description="Execute rustybt strategy")
    parser.add_argument("--strategy", required=True, help="Strategy module.class path")
    parser.add_argument("--data", required=True, type=Path, help="Data fixture path")
    parser.add_argument("--output", required=True, type=Path, help="Log output path")
    parser.add_argument("--params", type=json.loads, default={}, help="Strategy params JSON")
    args = parser.parse_args()

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Import strategy class
    strategy_class = import_strategy(args.strategy)

    # Load data
    data = load_data(args.data)

    try:
        # Execute strategy with logging
        strategy = strategy_class(log_path=args.output, **args.params)
        # Run backtest (implementation depends on rustybt API)
        run_backtest(strategy, data)
        sys.exit(0)
    except Exception as e:
        print(f"Execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**execute_backtrader.py**:
```python
"""CLI wrapper for Backtrader strategy execution."""
import argparse
import importlib
import json
import sys
from pathlib import Path

import backtrader as bt


def import_strategy(module_path: str):
    """Import strategy class from dotted module path."""
    parts = module_path.rsplit(".", 1)
    if len(parts) == 2:
        module_name, class_name = parts
    else:
        module_name = parts[0]
        class_name = "Strategy"

    try:
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        print(f"Could not import strategy: {module_path}", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Execute Backtrader strategy")
    parser.add_argument("--strategy", required=True, help="Strategy module.class path")
    parser.add_argument("--data", required=True, type=Path, help="Data fixture path")
    parser.add_argument("--output", required=True, type=Path, help="Log output path")
    parser.add_argument("--params", type=json.loads, default={}, help="Strategy params JSON")
    args = parser.parse_args()

    if not args.data.exists():
        print(f"Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    strategy_class = import_strategy(args.strategy)

    try:
        # Create Cerebro engine
        cerebro = bt.Cerebro()

        # Load data - Backtrader needs data adapter
        # Note: May need custom Parquet feed or convert to CSV
        data = load_backtrader_data(args.data)
        cerebro.adddata(data)

        # Add strategy with params including log_path
        cerebro.addstrategy(strategy_class, log_path=args.output, **args.params)

        # Run
        cerebro.run()
        sys.exit(0)
    except Exception as e:
        print(f"Execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def load_backtrader_data(data_path: Path):
    """Load Parquet data into Backtrader feed."""
    # Option 1: Use bt.feeds.PandasData with Polars → Pandas conversion
    import polars as pl
    df = pl.read_parquet(data_path).to_pandas()

    # Backtrader expects specific column names
    # Adjust as needed based on data schema
    return bt.feeds.PandasData(dataname=df)


if __name__ == "__main__":
    main()
```

### Project Structure Notes

**Files to create**:
- `rustybt/validation/execute_rustybt.py` (NEW - rustybt CLI wrapper)
- `rustybt/validation/execute_backtrader.py` (NEW - Backtrader CLI wrapper)
- `tests/validation/test_execute_scripts.py` (NEW - unit tests)

**Dependencies**:
- Backtrader (for execute_backtrader.py)
- Polars (for data loading)

### Testing Guidance

**Test argument parsing**:
```python
import subprocess
import sys

def test_rustybt_missing_strategy():
    result = subprocess.run(
        [sys.executable, "-m", "rustybt.validation.execute_rustybt",
         "--data", "/tmp/test.parquet", "--output", "/tmp/test.jsonl"],
        capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower()
```

### References

- [Source: docs/architecture.md - Subprocess Isolation Pattern (pg 249-268)]
- [Source: docs/epics.md - Story 2.5 specification]
- [Source: docs/sprint-artifacts/2-4-strategy-comparison-infrastructure-story-4.md]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/2-5-strategy-comparison-infrastructure-story-5.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Created execute_rustybt.py with CLI wrapper for rustybt strategy execution
- Created execute_backtrader.py with CLI wrapper for Backtrader strategy execution
- Both scripts use identical argument interfaces: --strategy, --data, --output, --params
- Implemented import_strategy() in both scripts to handle dotted module paths
- Added robust data loading in execute_backtrader.py to handle multi-asset Parquet files
- Fixed Backtrader params inheritance issue in simple_strategy.py

### Completion Notes List

- ✅ Created `rustybt/validation/execute_rustybt.py` - CLI wrapper for rustybt
- ✅ Created `rustybt/validation/execute_backtrader.py` - CLI wrapper for Backtrader
- ✅ Both scripts validate inputs: module exists, data file exists, output dir created
- ✅ Both scripts use identical CLI arguments (--strategy, --data, --output, --params)
- ✅ Error messages include context (module path, file path, traceback)
- ✅ Exit code 0 on success, 1 on failure
- ✅ Created comprehensive unit tests in `tests/validation/test_execute_scripts.py` (17 tests)
- ✅ All 146 validation tests pass with no regressions

### File List

**New Files:**
- `rustybt/validation/execute_rustybt.py` - CLI wrapper for rustybt strategy execution
- `rustybt/validation/execute_backtrader.py` - CLI wrapper for Backtrader strategy execution
- `tests/validation/test_execute_scripts.py` - Unit tests for CLI wrappers

**Modified Files:**
- `tests/validation/strategies/bt_strategies/simple_strategy.py` - Fixed params inheritance

---

## Review Section

### Code Review Summary (2025-11-26)

**Reviewer:** Senior Developer (Code Review Workflow)
**Status:** ✅ **APPROVED**

#### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC1: execute_rustybt.py | ✅ PASS | `rustybt/validation/execute_rustybt.py:1-222` - Full CLI implementation |
| AC2: execute_backtrader.py | ✅ PASS | `execute_backtrader.py:1-302` - Cerebro engine integration |
| AC3: Input validation | ✅ PASS | Both scripts check module imports, file existence, create output dirs |
| AC4: Identical parameter names | ✅ PASS | --strategy, --data, --output, --params in both |
| AC5: Clear error messages | ✅ PASS | "Could not import strategy", "Data file not found", tracebacks |
| AC6: Unit tests | ✅ PASS | 17 tests in test_execute_scripts.py |

#### Code Quality Assessment

**Strengths:**
1. **Robust data loading** - execute_backtrader.py handles multi-asset Parquet, datetime columns, column normalization
2. **Module path parsing** - rsplit('.', 1) correctly handles nested modules
3. **Output dir creation** - `args.output.parent.mkdir(parents=True, exist_ok=True)`
4. **Informative errors** - Includes module path, file path, and full traceback on failure
5. **Clean exit codes** - sys.exit(0) success, sys.exit(1) failure

**execute_backtrader.py Notable Features:**
- Normalizes column names to lowercase (line 125)
- Handles multi-asset filtering (lines 128-136)
- Detects datetime column (timestamp, datetime, or date) (lines 139-146)
- Converts datetime for Pandas index (lines 156-161)

#### Test Results

```
tests/validation/test_execute_scripts.py: 17 tests PASSED
```

Key tests:
- `TestExecuteRustybtCLI`: 8 tests
- `TestExecuteBacktraderCLI`: 6 tests
- `TestBothScriptsConsistency`: 2 tests (same required/optional args)
- `TestCLIErrorMessages`: 1 test

#### Recommended Actions

**No blocking issues identified.**

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-25 | Story drafted from epics.md specification | SM Agent |
| 2025-11-25 | Implementation complete - all ACs satisfied | Dev Agent |
| 2025-11-26 | Code review completed - APPROVED | Code Review Workflow |
