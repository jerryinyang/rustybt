# Epic 2: Strategy Comparison Infrastructure

**Goal:** Enable execution of identical strategies in both rustybt and Backtrader with structured log capture for comparison.

**Architecture References:**
- Log-Based Validation Architecture (Architecture pg 149-248)
- Subprocess Isolation Pattern (Architecture pg 249-268)
- ValidatedStrategy Base Classes (Architecture pg 163-179)

**Value:** Developers can execute dual strategies and capture structured logs for automated comparison.

**FRs Covered:** FR23-FR30 (Strategy Comparison Infrastructure - 8 FRs)

---

## Story 2.1: Implement ValidatedStrategy Base Class for rustybt

As a developer,
I want a base strategy class that auto-logs lifecycle events,
So that rustybt strategies automatically produce structured logs for comparison.

**Acceptance Criteria:**

**Given** the `rustybt/validation/base_strategy.py` module
**When** RustyBTValidatedStrategy is implemented
**Then** it extends rustybt's TradingAlgorithm with automatic logging:

```python
class RustyBTValidatedStrategy(TradingAlgorithm):
    """Base class for validated rustybt strategies with auto-logging."""

    def __init__(self, log_path: Path):
        self._log_path = log_path
        self._log_file = open(log_path, 'w')
        super().__init__()

    def _log_event(self, layer: str, event: str, data: dict) -> None:
        """Write structured event to JSONL log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "layer": layer,
            "event": event,
            "asset": data.get("asset"),
            "data": data
        }
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    def initialize(self, context):
        self._log_event("data", "initialize", {"context": "strategy_init"})
        super().initialize(context)

    def handle_data(self, context, data):
        self._log_event("data", "bar_received", {
            "timestamp": str(context.current_dt),
            "bar_count": len(data.history(data.current, "close", 1))
        })
        super().handle_data(context, data)
```

**And** lifecycle methods auto-log to appropriate layers:
- `initialize()` → layer: "data", event: "initialize"
- `handle_data()` → layer: "data", event: "bar_received"
- Signal computations → layer: "signals", event: "signal_computed"
- Order creation → layer: "orders", event: "order_created"

**And** log file is closed on strategy completion:
```python
def __del__(self):
    if hasattr(self, '_log_file') and not self._log_file.closed:
        self._log_file.close()
```

**And** unit tests verify logging behavior

**Prerequisites:** Story 1.3 (data models for log schema)

**Technical Notes:**
- Reference Architecture ValidatedStrategy Base Classes (pg 163-179)
- JSONL format: one JSON object per line
- Flush after each write to prevent data loss on crash
- Use context manager pattern for file handling

---

## Story 2.2: Implement ValidatedStrategy Base Class for Backtrader

As a developer,
I want a Backtrader base strategy class with identical logging behavior,
So that Backtrader strategies produce logs in the same format as rustybt.

**Acceptance Criteria:**

**Given** the `tests/validation/strategies/backtrader/base_validated.py` module
**When** BacktraderValidatedStrategy is implemented
**Then** it extends bt.Strategy with automatic logging:

```python
import backtrader as bt
from pathlib import Path
import json
from datetime import datetime

class BacktraderValidatedStrategy(bt.Strategy):
    """Base class for validated Backtrader strategies with auto-logging."""

    params = (
        ('log_path', None),
    )

    def __init__(self):
        self._log_file = open(self.params.log_path, 'w')
        self._log_event("data", "initialize", {"params": dict(self.params._getkwargs())})
        super().__init__()

    def _log_event(self, layer: str, event: str, data: dict) -> None:
        """Write structured event to JSONL log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "layer": layer,
            "event": event,
            "asset": data.get("asset"),
            "data": data
        }
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    def next(self):
        self._log_event("data", "bar_received", {
            "timestamp": str(self.data.datetime.datetime()),
            "close": float(self.data.close[0]),
            "volume": float(self.data.volume[0])
        })

    def stop(self):
        self._log_file.close()
```

**And** logging matches rustybt schema exactly:
- Same field names: timestamp, layer, event, asset, data
- Same layer values: data, signals, orders, broker, portfolio
- Same event names for equivalent operations

**And** file cleanup occurs in `stop()` method (Backtrader lifecycle)

**And** unit tests verify log format matches rustybt format

**Prerequisites:** Story 2.1 (rustybt base class defines schema)

**Technical Notes:**
- Reference Architecture Backtrader integration (pg 163-179)
- Backtrader uses `next()` instead of `handle_data()`
- Backtrader uses `stop()` for cleanup instead of destructor
- Use `self.params` for configuration (Backtrader convention)
- Access data via `self.data.close[0]` syntax

---

## Story 2.3: Create Log Event Decorators for Custom Logic

As a developer,
I want decorators to log custom strategy logic,
So that strategies can log signals, orders, and portfolio events without boilerplate.

**Acceptance Criteria:**

**Given** the `rustybt/validation/decorators.py` module
**When** logging decorators are implemented
**Then** the following decorators are available:

**@log_signal decorator:**
```python
def log_signal(layer: str = "signals"):
    """Decorator to log signal computation results."""
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            self._log_event(layer, "signal_computed", {
                "signal_name": method.__name__,
                "signal_value": result,
                "args": str(args),
            })
            return result
        return wrapper
    return decorator
```

**@log_order decorator:**
```python
def log_order(layer: str = "orders"):
    """Decorator to log order creation."""
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            order = method(self, *args, **kwargs)
            self._log_event(layer, "order_created", {
                "order_type": type(order).__name__,
                "asset": str(order.asset) if order else None,
                "quantity": float(order.quantity) if order else None,
                "limit_price": float(order.limit_price) if hasattr(order, 'limit_price') else None,
            })
            return order
        return wrapper
    return decorator
```

**@log_portfolio decorator:**
```python
def log_portfolio(layer: str = "portfolio"):
    """Decorator to log portfolio state."""
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            self._log_event(layer, "portfolio_updated", {
                "portfolio_value": float(self.portfolio.portfolio_value),
                "cash": float(self.portfolio.cash),
                "positions": {str(k): float(v.amount) for k, v in self.portfolio.positions.items()},
            })
            return result
        return wrapper
    return decorator
```

**And** decorators work with both rustybt and Backtrader base classes

**And** decorators handle exceptions gracefully (log failure, re-raise)

**And** unit tests demonstrate decorator usage in sample strategies

**Prerequisites:** Story 2.1, Story 2.2 (base classes with `_log_event()`)

**Technical Notes:**
- Use `functools.wraps` to preserve method metadata
- Convert Decimal/float values consistently in logs
- Handle None returns gracefully
- Decorators should be optional - strategies can call `_log_event()` directly

---

## Story 2.4: Implement Subprocess Execution Runner

As a developer,
I want a runner that executes strategies in isolated subprocesses,
So that rustybt and Backtrader don't conflict during execution.

**Acceptance Criteria:**

**Given** the `rustybt/validation/runner.py` module
**When** strategy runners are implemented
**Then** they support subprocess execution:

**run_rustybt_strategy() function:**
```python
def run_rustybt_strategy(
    strategy_module: str,
    data_path: Path,
    output_log: Path,
    params: dict = None
) -> subprocess.CompletedProcess:
    """Execute rustybt strategy in subprocess."""
    cmd = [
        sys.executable, "-m", "rustybt.validation.execute_rustybt",
        "--strategy", strategy_module,
        "--data", str(data_path),
        "--output", str(output_log),
    ]
    if params:
        cmd.extend(["--params", json.dumps(params)])

    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

**run_backtrader_strategy() function:**
```python
def run_backtrader_strategy(
    strategy_module: str,
    data_path: Path,
    output_log: Path,
    params: dict = None
) -> subprocess.CompletedProcess:
    """Execute Backtrader strategy in subprocess."""
    cmd = [
        sys.executable, "-m", "rustybt.validation.execute_backtrader",
        "--strategy", strategy_module,
        "--data", str(data_path),
        "--output", str(output_log),
    ]
    if params:
        cmd.extend(["--params", json.dumps(params)])

    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

**And** execution scripts exist:
- `rustybt/validation/execute_rustybt.py` - CLI wrapper for rustybt execution
- `rustybt/validation/execute_backtrader.py` - CLI wrapper for Backtrader execution

**And** runners capture stdout/stderr for error diagnostics

**And** runners enforce timeout (default 300 seconds)

**And** runners return exit code for success/failure detection

**And** integration test executes a simple strategy in both frameworks

**Prerequisites:** Story 2.1, Story 2.2 (base classes), Story 1.4 (test data)

**Technical Notes:**
- Reference Architecture Subprocess Isolation Pattern (pg 249-268)
- Use `subprocess.run()` for synchronous execution
- Use `sys.executable` to ensure same Python interpreter
- Timeout prevents hanging processes
- Capture output for debugging failed runs

---

## Story 2.5: Create Strategy Execution Wrapper Scripts

As a developer,
I want CLI wrapper scripts for each framework,
So that subprocess runners can execute strategies with consistent interfaces.

**Acceptance Criteria:**

**Given** the execution wrapper scripts
**When** they are implemented
**Then** `rustybt/validation/execute_rustybt.py` provides:

```python
"""CLI wrapper for rustybt strategy execution."""
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, help="Strategy module path")
    parser.add_argument("--data", required=True, type=Path, help="Data fixture path")
    parser.add_argument("--output", required=True, type=Path, help="Log output path")
    parser.add_argument("--params", type=json.loads, default={}, help="Strategy params JSON")
    args = parser.parse_args()

    # Import strategy class from module
    strategy_class = import_strategy(args.strategy)

    # Load data from Parquet
    data = load_data(args.data)

    # Execute strategy with logging
    strategy = strategy_class(log_path=args.output, **args.params)
    run_backtest(strategy, data)

if __name__ == "__main__":
    main()
```

**And** `rustybt/validation/execute_backtrader.py` provides equivalent Backtrader execution:

```python
"""CLI wrapper for Backtrader strategy execution."""
import argparse
import json
from pathlib import Path
import backtrader as bt

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, help="Strategy module path")
    parser.add_argument("--data", required=True, type=Path, help="Data fixture path")
    parser.add_argument("--output", required=True, type=Path, help="Log output path")
    parser.add_argument("--params", type=json.loads, default={}, help="Strategy params JSON")
    args = parser.parse_args()

    # Import strategy class from module
    strategy_class = import_strategy(args.strategy)

    # Create Cerebro engine
    cerebro = bt.Cerebro()

    # Load data
    data = bt.feeds.ParquetData(dataname=str(args.data))
    cerebro.adddata(data)

    # Add strategy with params
    cerebro.addstrategy(strategy_class, log_path=args.output, **args.params)

    # Run
    cerebro.run()

if __name__ == "__main__":
    main()
```

**And** both scripts:
- Exit with code 0 on success
- Exit with code 1 on failure (with error message to stderr)
- Validate all paths exist before execution
- Handle import errors gracefully

**And** unit tests verify CLI argument parsing

**Prerequisites:** Story 2.4 (runner functions)

**Technical Notes:**
- Use `importlib` for dynamic strategy import
- Backtrader may need data adapter (Parquet → bt.feeds)
- Both scripts should use identical parameter names for consistency
- Error messages should be clear and actionable

---

## Story 2.6: Implement Log Schema Validation

As a developer,
I want validation that log files follow the expected schema,
So that comparison can detect malformed logs before processing.

**Acceptance Criteria:**

**Given** the `rustybt/validation/log_parser.py` module
**When** schema validation is implemented
**Then** the following validation functions exist:

**validate_log_schema() function:**
```python
def validate_log_schema(log_path: Path) -> ValidationResult:
    """Validate JSONL log file against expected schema."""
    errors = []
    line_count = 0

    with open(log_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line_count += 1
            try:
                entry = json.loads(line)

                # Required fields
                if "timestamp" not in entry:
                    errors.append(f"Line {line_num}: Missing 'timestamp' field")
                if "layer" not in entry:
                    errors.append(f"Line {line_num}: Missing 'layer' field")
                if "event" not in entry:
                    errors.append(f"Line {line_num}: Missing 'event' field")

                # Valid layer values
                valid_layers = {"data", "signals", "orders", "broker", "portfolio"}
                if entry.get("layer") not in valid_layers:
                    errors.append(f"Line {line_num}: Invalid layer '{entry.get('layer')}'")

            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")

    return ValidationResult(
        valid=len(errors) == 0,
        line_count=line_count,
        errors=errors
    )
```

**And** ValidationResult dataclass:
```python
@dataclass
class ValidationResult:
    valid: bool
    line_count: int
    errors: list[str]
```

**And** CLI command for validation:
```bash
rustybt-validate log validate <log_path>
# Output: ✓ Valid (1234 lines) or ✗ Invalid (5 errors)
```

**And** validation runs automatically before comparison

**And** unit tests cover:
- Valid log files pass
- Missing required fields detected
- Invalid JSON detected
- Invalid layer values detected

**Prerequisites:** Story 2.1, Story 2.2 (log schema defined by base classes)

**Technical Notes:**
- Reference Architecture Log Schema (pg 183-189)
- Stream file to handle large logs without loading into memory
- Collect all errors (don't stop at first error)
- Provide actionable error messages with line numbers

---

## Story 2.7: Implement Dual Framework Execution Coordinator

As a developer,
I want a coordinator that executes both frameworks and collects logs,
So that validation can be performed with a single command.

**Acceptance Criteria:**

**Given** the `rustybt/validation/coordinator.py` module
**When** execution coordinator is implemented
**Then** it provides:

**execute_dual() function:**
```python
def execute_dual(
    session: Session,
    strategy_name: str,
    rustybt_module: str,
    backtrader_module: str,
    params: dict = None
) -> ExecutionResult:
    """Execute strategy in both frameworks and collect logs."""

    # Create log paths
    logs_dir = Path(f"validation-sessions/{session.id}/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    rustybt_log = logs_dir / "rustybt.jsonl"
    backtrader_log = logs_dir / "backtrader.jsonl"

    # Execute rustybt
    rb_result = run_rustybt_strategy(
        strategy_module=rustybt_module,
        data_path=session.data_fixture,
        output_log=rustybt_log,
        params=params
    )

    # Execute Backtrader
    bt_result = run_backtrader_strategy(
        strategy_module=backtrader_module,
        data_path=session.data_fixture,
        output_log=backtrader_log,
        params=params
    )

    # Validate logs
    rb_valid = validate_log_schema(rustybt_log)
    bt_valid = validate_log_schema(backtrader_log)

    return ExecutionResult(
        rustybt_success=rb_result.returncode == 0,
        backtrader_success=bt_result.returncode == 0,
        rustybt_log=rustybt_log,
        backtrader_log=backtrader_log,
        rustybt_log_valid=rb_valid.valid,
        backtrader_log_valid=bt_valid.valid,
        errors=collect_errors(rb_result, bt_result, rb_valid, bt_valid)
    )
```

**And** ExecutionResult dataclass:
```python
@dataclass
class ExecutionResult:
    rustybt_success: bool
    backtrader_success: bool
    rustybt_log: Path
    backtrader_log: Path
    rustybt_log_valid: bool
    backtrader_log_valid: bool
    errors: list[str]

    @property
    def success(self) -> bool:
        return (self.rustybt_success and self.backtrader_success and
                self.rustybt_log_valid and self.backtrader_log_valid)
```

**And** CLI command:
```bash
rustybt-validate run <session_id>
# Output: ✓ Both frameworks executed successfully
#         - rustybt: 1234 log entries
#         - backtrader: 1256 log entries
```

**And** execution updates session status

**And** integration test validates full execution flow

**Prerequisites:** Story 2.4 (runners), Story 2.5 (wrappers), Story 2.6 (validation)

**Technical Notes:**
- Execute sequentially (not parallel) for determinism
- Collect all errors for comprehensive diagnostics
- Update session.yaml with execution results
- Support --dry-run flag for testing without execution

---
