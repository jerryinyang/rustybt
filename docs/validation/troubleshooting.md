# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the rustybt validation framework.

## Quick Diagnostics

Before diving into specific issues, run these diagnostic commands:

```bash
# Check Python version (requires 3.12+)
python --version

# Verify rustybt is installed
pip show rustybt

# Check for Backtrader
pip show backtrader

# List validation sessions
rustybt-validate session list

# Check session health
rustybt-validate session show <session_id>
```

---

## Installation Issues

### Python Version Mismatch

**Symptom:**
```
ERROR: This package requires Python >=3.12
```
or
```
SyntaxError: invalid syntax (due to 3.12+ features like type parameter syntax)
```

**Cause:**
rustybt requires Python 3.12 or later. You may be running an older Python version.

**Resolution:**
1. Check your Python version:
   ```bash
   python --version
   python3 --version
   ```

2. Install Python 3.12+:
   - macOS: `brew install python@3.12`
   - Ubuntu: `sudo apt install python3.12`
   - Windows: Download from python.org

3. Create a virtual environment with the correct version:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   pip install rustybt
   ```

### Backtrader Installation Conflicts

**Symptom:**
```
ModuleNotFoundError: No module named 'backtrader'
```
or
```
ImportError: cannot import name 'xxx' from 'backtrader'
```

**Cause:**
Backtrader is not installed, or an incompatible version is installed.

**Resolution:**
1. Install Backtrader:
   ```bash
   pip install backtrader
   ```

2. If you have version conflicts, pin the version:
   ```bash
   pip install backtrader==1.9.76.123
   ```

3. Verify installation:
   ```bash
   python -c "import backtrader; print(backtrader.__version__)"
   ```

### Dependency Version Conflicts

**Symptom:**
```
ERROR: pip's dependency resolver does not currently take into account all packages
```
or
```
Conflicting dependencies for package X
```

**Cause:**
Your environment has packages with conflicting version requirements.

**Resolution:**
1. Create a fresh virtual environment:
   ```bash
   python3.12 -m venv .venv-fresh
   source .venv-fresh/bin/activate
   ```

2. Install rustybt in the clean environment:
   ```bash
   pip install rustybt
   ```

3. If conflicts persist, check for problematic packages:
   ```bash
   pip check
   ```

4. Consider using `pip install --upgrade-strategy eager` to update all dependencies.

### Virtual Environment Issues

**Symptom:**
```
Command 'rustybt-validate' not found
```
or commands run with wrong Python version.

**Cause:**
Virtual environment not activated, or rustybt installed in different environment.

**Resolution:**
1. Activate your virtual environment:
   ```bash
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

2. Verify you're in the right environment:
   ```bash
   which python  # Should point to .venv
   pip show rustybt
   ```

3. Reinstall if needed:
   ```bash
   pip install --force-reinstall rustybt
   ```

---

## Strategy Execution Failures

### Subprocess Exit Code Errors

**Symptom:**
```
✗ Error: Subprocess returned non-zero exit code: 1
```
or
```
Strategy execution failed with exit code N
```

**Cause:**
The strategy script raised an exception or had an error during execution.

**Resolution:**
1. Run the strategy directly to see the full error:
   ```bash
   python strategies/my_strategy.py
   ```

2. Check for common issues:
   - Missing imports
   - Incorrect data paths
   - Strategy configuration errors

3. Enable verbose logging:
   ```bash
   rustybt-validate run my_strategy --verbose
   ```

4. Check the session's error log:
   ```bash
   cat .validation/sessions/<session_id>/errors.log
   ```

### Strategy Import Failures

**Symptom:**
```
ModuleNotFoundError: No module named 'my_strategy'
```
or
```
ImportError: cannot import name 'MyStrategy' from 'strategies'
```

**Cause:**
The strategy module cannot be found or has import errors.

**Resolution:**
1. Verify the strategy file exists:
   ```bash
   ls -la strategies/my_strategy.py
   ```

2. Check your PYTHONPATH:
   ```bash
   echo $PYTHONPATH
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

3. Verify the strategy class is correctly defined:
   ```python
   # Should have a class inheriting from appropriate base
   class MyStrategy:
       def __init__(self):
           pass
   ```

4. Test the import directly:
   ```bash
   python -c "from strategies.my_strategy import MyStrategy"
   ```

### Log File Not Generated

**Symptom:**
```
✗ Error: Log file not found at expected path
```
or comparison fails with missing log file.

**Cause:**
The strategy completed but didn't generate validation logs.

**Resolution:**
1. Check if the strategy has logging enabled:
   ```python
   # Strategy should use the validation logger
   from rustybt.validation import ValidationLogger
   logger = ValidationLogger()
   ```

2. Verify the log output directory exists:
   ```bash
   ls -la .validation/sessions/<session_id>/logs/
   ```

3. Check file permissions:
   ```bash
   touch .validation/sessions/<session_id>/logs/test.log
   ```

4. Run with explicit log path:
   ```bash
   rustybt-validate run my_strategy --log-dir ./custom_logs
   ```

### Timeout and Memory Issues

**Symptom:**
```
✗ Error: Strategy execution timed out after 300 seconds
```
or
```
MemoryError: Unable to allocate X bytes
```

**Cause:**
The strategy is taking too long or consuming too much memory.

**Resolution:**
1. Increase timeout (for legitimate long-running strategies):
   ```bash
   rustybt-validate run my_strategy --timeout 600
   ```

2. Reduce data size for testing:
   - Use smaller date ranges
   - Test with fewer symbols

3. Profile memory usage:
   ```bash
   python -m memory_profiler strategies/my_strategy.py
   ```

4. Consider chunking large data operations in your strategy.

---

## Log Parsing Errors

### JSONL Schema Validation Errors

**Symptom:**
```
✗ Error: Missing required field 'layer' in log entry
```
or
```
Schema validation failed: expected field 'timestamp'
```

**Cause:**
Log entries don't conform to the expected schema.

**Resolution:**
1. Validate the log file:
   ```bash
   rustybt-validate log validate <log_file>
   ```

2. Check log entry format (should be JSONL with required fields):
   ```json
   {"layer": "data", "event": "bar", "timestamp": "2024-01-15T09:30:00", ...}
   ```

3. Required fields for each log entry:
   - `layer`: One of "data", "signals", "orders", "broker", "portfolio"
   - `event`: Event type (e.g., "bar", "signal", "order", "fill", "portfolio_update")
   - `timestamp`: ISO 8601 timestamp

4. Use the log inspector to find problematic lines:
   ```bash
   head -20 logs/rustybt.jsonl | python -m json.tool --compact
   ```

### Incomplete Log File Issues

**Symptom:**
```
✗ Error: Log file is incomplete (no END marker)
```
or health check shows truncated file.

**Cause:**
Strategy execution was interrupted before completing, leaving a partial log.

**Resolution:**
1. Re-run the strategy to generate a complete log:
   ```bash
   rustybt-validate run my_strategy --force
   ```

2. Check for crashes in the strategy:
   ```bash
   cat .validation/sessions/<session_id>/errors.log
   ```

3. Verify disk space:
   ```bash
   df -h .
   ```

4. If intentionally interrupted, consider using the partial log with caution:
   ```bash
   rustybt-validate compare <session_id> --allow-incomplete
   ```

### Encoding/Charset Issues

**Symptom:**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xXX
```

**Cause:**
Log file contains non-UTF-8 characters.

**Resolution:**
1. Detect the file encoding:
   ```bash
   file --mime-encoding logs/rustybt.jsonl
   ```

2. Convert to UTF-8:
   ```bash
   iconv -f ISO-8859-1 -t UTF-8 logs/rustybt.jsonl > logs/rustybt_utf8.jsonl
   ```

3. Ensure your strategy writes UTF-8:
   ```python
   with open(log_path, 'w', encoding='utf-8') as f:
       json.dump(data, f, ensure_ascii=False)
   ```

### Malformed JSON Line Errors

**Symptom:**
```
✗ Error: Invalid JSON at line N
```
or
```
json.JSONDecodeError: Expecting property name: line 1 column 42
```

**Cause:**
One or more lines in the JSONL file contain invalid JSON.

**Resolution:**
1. Find the problematic line:
   ```bash
   # Show line N (replace N with the line number)
   sed -n 'Np' logs/rustybt.jsonl
   ```

2. Validate each line:
   ```bash
   cat logs/rustybt.jsonl | while read line; do
     echo "$line" | python -m json.tool > /dev/null || echo "Invalid: $line"
   done
   ```

3. Common issues:
   - Trailing commas: `{"key": "value",}`
   - Unquoted strings: `{key: "value"}`
   - Single quotes: `{'key': 'value'}`
   - Embedded newlines in strings

4. Use the health check for details:
   ```python
   from rustybt.validation.health_checks import validate_log_integrity
   from pathlib import Path

   result = validate_log_integrity(Path("logs/rustybt.jsonl"))
   print(result.diagnostics)
   ```

---

## Comparison Failures

### Tolerance Threshold Issues

**Symptom:**
```
✗ Discrepancy: price differs by 0.0002 (tolerance: 0.0001)
```
or many findings due to small numerical differences.

**Cause:**
Tolerance thresholds are too strict for the comparison being performed.

**Resolution:**
1. View current tolerances:
   ```bash
   rustybt-validate config show
   ```

2. Adjust tolerances in `tolerances.yaml`:
   ```yaml
   layer_1_data:
     price_decimal_places: 3  # Less strict (was 4)
     volume_tolerance_pct: 0.01  # Allow 1% difference
   ```

3. Use tolerance overrides for specific comparisons:
   ```python
   from rustybt.validation.tolerance import ToleranceConfig

   config = ToleranceConfig()
   relaxed = config.with_overrides(layer_1_price_decimal_places=3)
   ```

4. Document why tolerances are adjusted (legitimate differences vs. bugs).

### Missing Data Field Errors

**Symptom:**
```
✗ Error: Field 'close' not found in Backtrader log
```
or
```
KeyError: 'expected_field'
```

**Cause:**
The log files have different fields or one is missing required data.

**Resolution:**
1. Compare log schemas:
   ```bash
   # Check first entry of each log
   head -1 logs/rustybt.jsonl | python -m json.tool
   head -1 logs/backtrader.jsonl | python -m json.tool
   ```

2. Ensure both frameworks log the same events:
   ```python
   # Both should log: open, high, low, close, volume
   logger.log_bar(symbol, datetime, open, high, low, close, volume)
   ```

3. Add missing fields to your strategy's logging:
   ```python
   # Include all required fields
   log_entry = {
       "layer": "data",
       "event": "bar",
       "timestamp": bar_time.isoformat(),
       "symbol": symbol,
       "open": float(bar.open),
       "high": float(bar.high),
       "low": float(bar.low),
       "close": float(bar.close),
       "volume": int(bar.volume)
   }
   ```

### Timestamp Alignment Failures

**Symptom:**
```
✗ Error: No matching timestamp in Backtrader log
```
or timestamps are off by a fixed amount.

**Cause:**
Frameworks are using different timestamp formats or timezone handling.

**Resolution:**
1. Check timestamp formats:
   ```bash
   grep timestamp logs/rustybt.jsonl | head -3
   grep timestamp logs/backtrader.jsonl | head -3
   ```

2. Ensure consistent timezone handling:
   ```python
   from datetime import timezone

   # Use UTC consistently
   timestamp = bar_time.replace(tzinfo=timezone.utc).isoformat()
   ```

3. Adjust timestamp tolerance if small differences are acceptable:
   ```yaml
   layer_1_data:
     timestamp_window_ms: 1000  # Allow 1 second difference
   ```

4. Verify both frameworks use the same bar timing convention (open vs close time).

### Unexpected Discrepancy Patterns

**Symptom:**
Systematic differences that follow a pattern (e.g., all prices off by 1 tick).

**Cause:**
Different calculation methodologies between frameworks.

**Resolution:**
1. Investigate the pattern:
   ```bash
   rustybt-validate investigate <session_id> --layer data
   ```

2. Document the discrepancy:
   ```bash
   rustybt-validate investigate <session_id> \
     --finding <finding_id> \
     --classification DESIGN \
     --reason "Backtrader uses different rounding convention"
   ```

3. Common causes of systematic differences:
   - Different default order types
   - Slippage/commission model differences
   - Data alignment conventions (forward vs backward fill)

4. If it's a bug, track it properly before moving on.

---

## Session Management Issues

### Session Not Found

**Symptom:**
```
✗ Error: Session not found: 20251124-143000-my_strategy
```

**Cause:**
The session doesn't exist or was deleted.

**Resolution:**
1. List all sessions:
   ```bash
   rustybt-validate session list
   ```

2. Check if the session was archived:
   ```bash
   ls .validation/archive/
   ```

3. Verify the session directory exists:
   ```bash
   ls .validation/sessions/
   ```

4. Create a new session if needed:
   ```bash
   rustybt-validate session create my_strategy
   ```

### Corrupted Session YAML

**Symptom:**
```
yaml.YAMLError: could not determine a constructor for the tag
```
or
```
✗ Error: Failed to load session: invalid YAML
```

**Cause:**
The session.yaml file is corrupted or malformed.

**Resolution:**
1. View the raw session file:
   ```bash
   cat .validation/sessions/<session_id>/session.yaml
   ```

2. Look for common YAML issues:
   - Tabs instead of spaces
   - Unclosed quotes
   - Invalid special characters

3. If recoverable, fix the YAML manually:
   ```yaml
   id: "20251124-143000-my_strategy"
   strategy: "my_strategy"
   stage: "COMPARISON"
   created: "2024-11-24T14:30:00"
   ```

4. If not recoverable, delete and recreate:
   ```bash
   rustybt-validate session delete <session_id>
   rustybt-validate session create my_strategy
   ```

### Session Resume Failures

**Symptom:**
```
✗ Error: Cannot resume session in FAILED state
```
or
```
✗ Error: Cannot resume completed session
```

**Cause:**
Session is in a terminal state (FAILED or COMPLETED).

**Resolution:**
1. Check session status:
   ```bash
   rustybt-validate session show <session_id>
   ```

2. For FAILED sessions, view the errors:
   ```bash
   cat .validation/sessions/<session_id>/errors.log
   ```

3. Create a new session instead:
   ```bash
   rustybt-validate session create my_strategy --force
   ```

4. For completed sessions that need re-validation:
   ```bash
   rustybt-validate session delete <session_id>
   rustybt-validate session create my_strategy
   ```

### Findings YAML Corruption

**Symptom:**
```
✗ Error: Failed to load findings: invalid YAML
```
or findings list shows unexpected data.

**Cause:**
The findings.yaml file is corrupted.

**Resolution:**
1. View the findings file:
   ```bash
   cat .validation/sessions/<session_id>/findings.yaml
   ```

2. Validate YAML syntax:
   ```bash
   python -c "import yaml; yaml.safe_load(open('.validation/sessions/<session_id>/findings.yaml'))"
   ```

3. If corrupt, you may need to re-run comparison:
   ```bash
   # Backup existing findings
   cp .validation/sessions/<session_id>/findings.yaml findings_backup.yaml

   # Clear findings and re-compare
   rm .validation/sessions/<session_id>/findings.yaml
   rustybt-validate compare <session_id>
   ```

### Duplicate Session Error

**Symptom:**
```
✗ Error: Session 20251124-143000-my_strategy already in progress for my_strategy.
Use 'rustybt-validate session resume 20251124-143000-my_strategy' to continue
or 'rustybt-validate session delete 20251124-143000-my_strategy' to start fresh.
```

**Cause:**
An IN_PROGRESS session already exists for this strategy.

**Resolution:**
1. Resume the existing session:
   ```bash
   rustybt-validate session resume 20251124-143000-my_strategy
   ```

2. Or delete and start fresh:
   ```bash
   rustybt-validate session delete 20251124-143000-my_strategy
   rustybt-validate session create my_strategy
   ```

3. Or force create (deletes existing):
   ```bash
   rustybt-validate session create my_strategy --force
   ```

---

## Error Messages Reference

### Installation Errors

| Error Message | Cause | Resolution |
|--------------|-------|------------|
| `ModuleNotFoundError: No module named 'rustybt'` | rustybt not installed | `pip install rustybt` |
| `ModuleNotFoundError: No module named 'backtrader'` | Backtrader not installed | `pip install backtrader` |
| `This package requires Python >=3.12` | Python too old | Install Python 3.12+ |

### Session Errors

| Error Message | Cause | Resolution |
|--------------|-------|------------|
| `Session not found: <id>` | Session doesn't exist | List sessions with `session list` |
| `Session <id> already in progress` | Duplicate session | Resume or delete existing session |
| `Cannot resume session in FAILED state` | Session failed | Check errors.log, create new session |
| `Cannot resume completed session` | Session already done | Delete and recreate if needed |

### Validation Errors

| Error Message | Cause | Resolution |
|--------------|-------|------------|
| `Log file is empty (0 records)` | Strategy didn't log | Verify logging is enabled |
| `Missing required field 'layer'` | Invalid log schema | Check log entry format |
| `Invalid JSON at line N` | Malformed JSON | Fix the JSON on line N |
| `No matching timestamp` | Timestamp mismatch | Check timezone handling |

### Configuration Errors

| Error Message | Cause | Resolution |
|--------------|-------|------------|
| `Tolerance config not found` | Missing config file | Create tolerances.yaml or use defaults |
| `Invalid YAML in config` | Malformed YAML | Fix YAML syntax |
| `timestamp_window_ms must be non-negative` | Invalid tolerance value | Use positive numbers |

---

## When to Escalate

### Report a Bug When:

1. **Crash without error message** - The framework crashes with no useful output
2. **Data corruption** - Session or findings data becomes corrupted during normal use
3. **Incorrect comparison results** - Obvious mismatches that should pass validation
4. **Documentation mismatch** - Behavior differs from what documentation describes
5. **Reproducible failures** - Issues that occur consistently with the same steps

### Before Reporting:

1. **Gather debug information:**
   ```bash
   # Collect version info
   pip show rustybt
   python --version

   # Collect session state
   rustybt-validate session show <session_id> > session_state.txt

   # Collect error logs
   cat .validation/sessions/<session_id>/errors.log > errors.txt
   ```

2. **Create minimal reproduction:**
   - Simplify the strategy to the minimum that triggers the issue
   - Note exact steps to reproduce

3. **Check existing issues:**
   - Search [GitHub Issues](https://github.com/rustybt/rustybt/issues) first

### Bug Report Requirements:

Include in your bug report:
- rustybt version (`pip show rustybt`)
- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages (full text)
- Relevant log files

### Submit Issues:

GitHub Issues: https://github.com/rustybt/rustybt/issues

---

## Getting Debug Information

### Enable Verbose Logging

```bash
rustybt-validate run my_strategy --verbose
```

### Inspect Session State

```bash
# Full session details
rustybt-validate session show <session_id>

# Session activities
rustybt-validate session activities <session_id>

# Session findings
rustybt-validate session findings <session_id>
```

### Check File Integrity

```python
from rustybt.validation.health_checks import validate_log_integrity
from pathlib import Path

result = validate_log_integrity(Path("logs/rustybt.jsonl"))
print(f"Passed: {result.passed}")
print(f"Diagnostics: {result.diagnostics}")
```

### Export Session Data

```bash
# Export to JSON for debugging
rustybt-validate report <session_id> --format json > session_debug.json
```

---

## See Also

- [Getting Started](getting-started.md) - Initial setup and first session
- [CLI Reference](cli-reference.md) - Complete command documentation
- [Python API Reference](python-api-reference.md) - Programmatic usage
- [Investigation Workflow Guide](investigation-workflow-guide.md) - Handling findings
