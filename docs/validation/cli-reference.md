# CLI Reference

Complete command-line interface reference for the rustybt validation framework.

## Global Options

```bash
rustybt-validate [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--version` | Show the version and exit |
| `--help` | Show help message and exit |

---

## Session Commands

Session management commands for creating, viewing, and managing validation sessions.

```bash
rustybt-validate session [COMMAND]
```

### session create

Create a new validation session.

```bash
rustybt-validate session create [OPTIONS]
```

**Options:**

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--strategy TEXT` | Yes | - | Strategy name (e.g., `sma_crossover`) |
| `--data PATH` | Yes | - | Path to data fixture (must exist) |
| `--rustybt-version TEXT` | No | `0.3.4` | rustybt version being validated |
| `--backtrader-version TEXT` | No | `1.9.78` | Backtrader version for reference |
| `--force` | No | False | Override existing IN_PROGRESS session (marks as SUPERSEDED) |

**Examples:**

```bash
# Create basic session
rustybt-validate session create \
    --strategy sma_crossover \
    --data tests/validation/fixtures/validation_data.parquet

# Create with specific versions
rustybt-validate session create \
    --strategy momentum \
    --data tests/validation/fixtures/validation_data.parquet \
    --rustybt-version 0.4.0 \
    --backtrader-version 1.9.78

# Override existing session
rustybt-validate session create \
    --strategy sma_crossover \
    --data tests/validation/fixtures/validation_data.parquet \
    --force
```

**Output:**

```
✓ Session created: 20251129-143000-sma_crossover
  Strategy: sma_crossover
  Data: tests/validation/fixtures/validation_data.parquet
```

**Error Handling:**

If a session already exists for the same strategy with IN_PROGRESS status:
```
✗ Error: Session already exists for strategy 'sma_crossover'

Suggested actions:
  • Resume existing session: rustybt-validate session resume 20251124-143000-sma_crossover
  • Delete existing session: rustybt-validate session delete 20251124-143000-sma_crossover
  • Override with --force:   rustybt-validate session create --strategy sma_crossover --data ... --force
```

---

### session list

List all validation sessions with optional filters.

```bash
rustybt-validate session list [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--strategy TEXT` | None | Filter by strategy name |
| `--status TEXT` | None | Filter by status (`IN_PROGRESS`, `COMPLETED`, `FAILED`) |
| `--stage TEXT` | None | Filter by stage (`created`, `executing`, `executed`, etc.) |
| `--since DATE` | None | Filter sessions created after date (YYYY-MM-DD) |
| `--has-findings` | False | Only show sessions with findings |
| `--format [table\|json]` | `table` | Output format |

**Examples:**

```bash
# List all sessions
rustybt-validate session list

# Filter by strategy
rustybt-validate session list --strategy sma_crossover

# Filter by status
rustybt-validate session list --status COMPLETED

# Filter by stage
rustybt-validate session list --stage investigating

# Sessions since a date with findings
rustybt-validate session list --since 2025-01-01 --has-findings

# JSON output
rustybt-validate session list --format json
```

**Table Output:**

```
Session ID                                    | Strategy             | Stage           | Status       | Created
------------------------------------------------------------------------------------------------------------------------
20251129-143000-sma_crossover                 | sma_crossover        | investigating   | IN_PROGRESS  | 2025-11-29 14:30:00
20251128-090000-momentum                      | momentum             | completed       | COMPLETED    | 2025-11-28 09:00:00
```

**JSON Output:**

```json
[
  {
    "id": "20251129-143000-sma_crossover",
    "strategy": "sma_crossover",
    "stage": "investigating",
    "status": "IN_PROGRESS",
    "created_at": "2025-11-29T14:30:00",
    "findings_count": 5
  }
]
```

---

### session show

Show details of a validation session.

```bash
rustybt-validate session show SESSION_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format [table\|json]` | `table` | Output format |

**Example:**

```bash
rustybt-validate session show 20251129-143000-sma_crossover
```

**Output:**

```
Session: 20251129-143000-sma_crossover
Strategy: sma_crossover
Status: IN_PROGRESS
Stage: investigating
Created: 2025-11-29 14:30:00

Progress:
  [x] Created completed (14:30:00)
  [x] Execution completed (14:31:15)
  [x] Comparison completed (14:31:45)
  [ ] Investigation in progress
  [ ] Completed

Findings: 5 total (3 BUG, 2 DESIGN)

Layers Completed: data, signals
Layers Pending: orders, broker, portfolio

rustybt Version: 0.3.4
Backtrader Version: 1.9.78
Python Version: 3.12.0
Data Fixture: tests/validation/fixtures/validation_data.parquet
Directory: validation-sessions/20251129-143000-sma_crossover/
```

---

### session resume

Resume an interrupted validation session.

```bash
rustybt-validate session resume SESSION_ID
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Example:**

```bash
rustybt-validate session resume 20251129-143000-sma_crossover
```

**Output:**

```
✓ Resuming session 20251129-143000-sma_crossover from stage: investigating
  Next step: Continue classifying findings
  Artifacts found: rustybt.jsonl, backtrader.jsonl
  Status: IN_PROGRESS
```

---

### session findings

List all findings for a validation session.

```bash
rustybt-validate session findings SESSION_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format [table\|json]` | `table` | Output format |

**Example:**

```bash
rustybt-validate session findings 20251129-143000-sma_crossover
```

**Output:**

```
Findings for session: 20251129-143000-sma_crossover
Total: 5

⚠ 2 unclassified finding(s)

ID              | Layer        | Classification  | Description
--------------------------------------------------------------------------------
FIND-001        | orders       | BUG             | Order fill price mismatch...
FIND-002        | broker       | DESIGN          | Commission calculation dif...
FIND-003        | portfolio    | -               | Portfolio value discrepanc...
```

---

### session activities

Show session activity log (audit trail).

```bash
rustybt-validate session activities SESSION_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format [table\|json]` | `table` | Output format |

**Example:**

```bash
rustybt-validate session activities 20251129-143000-sma_crossover
```

**Output:**

```
Activity log for session: 20251129-143000-sma_crossover
Total activities: 8

Timestamp            | Actor      | Action
--------------------------------------------------------------------------------
2025-11-29 14:30:00  | system     | session_created
2025-11-29 14:30:05  | system     | stage_changed: executing
2025-11-29 14:31:15  | system     | execution_completed
2025-11-29 14:31:20  | system     | stage_changed: compared
2025-11-29 14:35:00  | user       | investigation_started: Starting investigation with 5 findings
```

---

### session delete

Delete a validation session and all its files.

```bash
rustybt-validate session delete SESSION_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--yes, -y` | False | Skip confirmation prompt |
| `--dry-run` | False | Show what would be deleted without deleting |

**Examples:**

```bash
# Interactive delete
rustybt-validate session delete 20251129-143000-sma_crossover

# Skip confirmation
rustybt-validate session delete 20251129-143000-sma_crossover --yes

# Preview what would be deleted
rustybt-validate session delete 20251129-143000-sma_crossover --dry-run
```

---

### session archive

Archive a validation session to compressed storage.

```bash
rustybt-validate session archive SESSION_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | False | Show what would be archived without archiving |

**Example:**

```bash
rustybt-validate session archive 20251129-143000-sma_crossover
```

**Output:**

```
✓ Session archived: 20251129-143000-sma_crossover
  Archive: validation-sessions/archive/20251129-143000-sma_crossover.tar.gz
```

---

### session cleanup

Clean up old sessions by deleting or archiving them.

```bash
rustybt-validate session cleanup [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--older-than DAYS` | None | Only clean sessions older than N days |
| `--status TEXT` | None | Only clean sessions with this status |
| `--archive` | False | Archive sessions instead of deleting |
| `--dry-run` | False | Preview what would be affected |
| `--yes, -y` | False | Skip confirmation prompt |

**Examples:**

```bash
# Delete sessions older than 30 days
rustybt-validate session cleanup --older-than 30

# Archive completed sessions older than 7 days
rustybt-validate session cleanup --older-than 7 --status COMPLETED --archive

# Delete all failed sessions
rustybt-validate session cleanup --status FAILED

# Preview what would be deleted
rustybt-validate session cleanup --older-than 30 --dry-run
```

---

## run

Execute validation for a session.

```bash
rustybt-validate run SESSION_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--rustybt-module TEXT` | Auto-detected | Python module path for rustybt strategy |
| `--backtrader-module TEXT` | Auto-detected | Python module path for Backtrader strategy |

**Default Module Paths:**
- rustybt: `tests.validation.strategies.rustybt.{strategy}`
- Backtrader: `tests.validation.strategies.bt_strategies.{strategy}`

**Examples:**

```bash
# Run with default module paths
rustybt-validate run 20251129-143000-sma_crossover

# Run with custom module paths
rustybt-validate run 20251129-143000-sma_crossover \
    --rustybt-module myproject.strategies.sma \
    --backtrader-module myproject.bt.sma
```

**Output:**

```
Executing sma_crossover...
  rustybt module: tests.validation.strategies.rustybt.sma_crossover
  Backtrader module: tests.validation.strategies.bt_strategies.sma_crossover

Execution completed:
  - rustybt: 1523 log entries
  - Backtrader: 1520 log entries
Session status updated: IN_PROGRESS
```

---

## compare

Run layer comparison and detect regressions.

```bash
rustybt-validate compare SESSION_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--layer, -l TEXT` | All layers | Specific layers to compare (can specify multiple) |

**Examples:**

```bash
# Compare all layers
rustybt-validate compare 20251129-143000-sma_crossover

# Compare specific layers
rustybt-validate compare 20251129-143000-sma_crossover --layer orders --layer broker
```

**Output:**

```
=== Comparing Session: 20251129-143000-sma_crossover ===

Strategy: sma_crossover
Status: IN_PROGRESS

Loading logs...
  rustybt: 1523 events
  Backtrader: 1520 events

Running comparisons...
  data: ✓ matched
  signals: ✓ matched
  orders: 3 discrepancies
  broker: 2 discrepancies
  portfolio: ✓ matched

Checking for regressions...
✓ No regressions detected

=== Summary ===
Total discrepancies: 5
Regressions: 0
New findings: 5

Next steps:
  1. Run 'rustybt-validate investigate' to classify discrepancies
  2. Fix any bugs identified
  3. Run 'rustybt-validate verify' to confirm fixes
```

---

## investigate

Investigate discrepancies in a validation session.

```bash
rustybt-validate investigate SESSION_ID [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Yes | Session identifier |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--finding TEXT` | None | Jump to specific finding ID (e.g., `FIND-001`) |
| `--layer [data\|signals\|orders\|broker\|portfolio]` | None | Filter findings to specific layer |
| `--unclassified` | False | Show only unclassified findings |
| `--bugs` | False | Show only BUG-classified findings |
| `--design` | False | Show only DESIGN-classified findings |

**Examples:**

```bash
# Investigate all findings
rustybt-validate investigate 20251129-143000-sma_crossover

# Jump to specific finding
rustybt-validate investigate 20251129-143000-sma_crossover --finding FIND-001

# Filter by layer
rustybt-validate investigate 20251129-143000-sma_crossover --layer orders

# Show only unclassified
rustybt-validate investigate 20251129-143000-sma_crossover --unclassified
```

**Interactive Commands:**

During investigation, the following single-key commands are available:

| Key | Action |
|-----|--------|
| `b` | Classify finding as **BUG** (with severity and affected components) |
| `d` | Classify finding as **DESIGN** (with rationale) |
| `s` | Skip finding and move to next |
| `v` | View source code locations |
| `c` | View comparison context |
| `n` | Next finding |
| `p` | Previous finding |
| `q` | Quit investigation |

**Investigation Display:**

```
Progress: [3/5] ██████░░░░ 60%

Finding: FIND-003
Layer: orders
Status: Unclassified

Description: Order fill price differs by 0.02%

rustybt Value: 152.35
Backtrader Value: 152.38

Context:
  Timestamp: 2025-11-15 10:30:00
  Asset: AAPL
  Order Type: MARKET

Actions: [b]ug [d]esign [s]kip [v]iew source [c]ontext [n]ext [p]rev [q]uit

Enter action: _
```

---

## verify

Verify a bug fix resolves the discrepancy.

```bash
rustybt-validate verify FINDING_ID
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `FINDING_ID` | Yes | Finding identifier (e.g., `FIND-001`) |

**Example:**

```bash
rustybt-validate verify FIND-001
```

**Output (Success):**

```
=== Verifying Fix for FIND-001 ===

Original discrepancy:
  Layer: orders
  Description: Order fill price mismatch
  rustybt: 152.35, Backtrader: 152.38

Re-running strategy execution...
✓ rustybt executed successfully
✓ Backtrader executed successfully

Re-running layer comparison...
✓ Original discrepancy no longer detected

=== Fix Verified ===
✓ Regression test created: tests/validation/regression/test_find_001.py
FIND-001 marked as resolved

Next steps:
  1. Run regression tests: pytest tests/validation/regression/ -v
  2. Commit the regression test to ensure CI catches future regressions
```

**Output (Failure):**

```
=== Verifying Fix for FIND-001 ===

Original discrepancy:
  Layer: orders
  Description: Order fill price mismatch
  rustybt: 152.35, Backtrader: 152.38

Re-running strategy execution...
✓ rustybt executed successfully
✓ Backtrader executed successfully

Re-running layer comparison...
✗ Verification failed
Discrepancy still present:
  rustybt: 152.35, Backtrader: 152.38

Fix not complete. Finding remains open.

Debugging suggestions:
  1. Check if the fix was applied to the correct file
  2. Review the comparison tolerance settings
  3. Use 'rustybt-validate investigate' to view more context
  4. Check files: rustybt/broker/execution.py
```

---

## report

Generate validation reports.

```bash
rustybt-validate report [SESSION_ID] [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SESSION_ID` | Conditional | Required unless `--layer` or `--strategy` specified |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format [markdown\|json]` | `markdown` | Output format |
| `--layer [data\|signals\|orders\|broker\|portfolio]` | None | Generate layer report |
| `--strategy TEXT` | None | Generate strategy report |

**Examples:**

```bash
# Session report
rustybt-validate report 20251129-143000-sma_crossover

# JSON format
rustybt-validate report 20251129-143000-sma_crossover --format json

# Layer report (aggregates across all strategies)
rustybt-validate report --layer signals

# Strategy report (shows all layers for one strategy)
rustybt-validate report --strategy sma_crossover
```

**Output:**

```
Report saved to: validation-sessions/20251129-143000-sma_crossover/report.md
  Session: 20251129-143000-sma_crossover
  Strategy: sma_crossover
  Status: IN_PROGRESS
  Findings: 5
```

---

## status

Show overall validation status dashboard.

```bash
rustybt-validate status [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f [ascii\|json]` | `ascii` | Output format |
| `--ci` | False | CI mode: return exit code based on health status |

**Examples:**

```bash
# ASCII dashboard
rustybt-validate status

# JSON output
rustybt-validate status --format json

# CI mode (exit code 0 if healthy, 1 if unhealthy)
rustybt-validate status --ci
```

**ASCII Output:**

```
╔═══════════════════════════════════════════════════════════════════╗
║                   VALIDATION STATUS DASHBOARD                      ║
╠═══════════════════════════════════════════════════════════════════╣
║ Strategy         │ Data │ Signals │ Orders │ Broker │ Portfolio   ║
╠──────────────────┼──────┼─────────┼────────┼────────┼─────────────╣
║ sma_crossover    │  ✓   │    ✓    │   ⚠    │   ⚠    │     ✓       ║
║ momentum         │  ✓   │    ✓    │   ✓    │   ✓    │     ✓       ║
║ mean_reversion   │  ✓   │    -    │   -    │   -    │     -       ║
╠═══════════════════════════════════════════════════════════════════╣
║ Findings: 5 total (3 BUG, 2 DESIGN)                                ║
║ Confidence Score: 78%                                              ║
╚═══════════════════════════════════════════════════════════════════╝

Legend: ✓ = Validated, ⚠ = Has findings, - = Pending
```

---

## progress

Show validation completion progress.

```bash
rustybt-validate progress
```

**Output:**

```
Validation Progress
═══════════════════

Strategies: ████████░░░░░░░░░░░░ 40% (2/5 completed)
Layers:     ██████████████░░░░░░ 72% (18/25 layers validated)
Findings:   ████████████████░░░░ 80% (4/5 classified)

Overall:    ████████████░░░░░░░░ 64%

Next Steps:
  1. Complete signals layer for mean_reversion
  2. Classify 1 unclassified finding
  3. Fix 3 open bugs
```

---

## next-actions

Show recommended next actions.

```bash
rustybt-validate next-actions
```

**Output:**

```
Recommended Next Actions
════════════════════════

Priority 1 - Fix Open Bugs:
  □ FIND-001: Order fill price mismatch (orders layer)
    → rustybt-validate investigate 20251129-143000-sma_crossover --finding FIND-001

  □ FIND-002: Commission calculation differs (broker layer)
    → rustybt-validate investigate 20251129-143000-sma_crossover --finding FIND-002

Priority 2 - Classify Unclassified Findings:
  □ FIND-005: Portfolio value discrepancy
    → rustybt-validate investigate 20251129-143000-sma_crossover --unclassified

Priority 3 - Complete Incomplete Strategies:
  □ mean_reversion: Only data layer validated
    → rustybt-validate run 20251128-100000-mean_reversion

Priority 4 - Update Documentation:
  □ Generate updated documentation
    → rustybt-validate docs generate
```

---

## docs

Documentation generation commands.

### docs generate

Generate documentation from validation findings.

```bash
rustybt-validate docs generate [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir, -o PATH` | `docs/validation` | Output directory |
| `--design-only` | False | Only generate design-differences.md |
| `--bugs-only` | False | Only generate bug-fixes.md |

**Examples:**

```bash
# Generate all documentation
rustybt-validate docs generate

# Custom output directory
rustybt-validate docs generate --output-dir ./docs/api

# Generate only design differences
rustybt-validate docs generate --design-only
```

**Output:**

```
✓ Generated: docs/validation/design-differences.md
✓ Generated: docs/validation/bug-fixes.md
```

### docs preview

Preview generated documentation without saving.

```bash
rustybt-validate docs preview [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--type, -t [design\|bugs]` | `design` | Document type to preview |

**Examples:**

```bash
# Preview design differences
rustybt-validate docs preview

# Preview bug fixes
rustybt-validate docs preview --type bugs
```

---

## config

Configuration management commands.

### config show

Show tolerance configuration for a validation layer.

```bash
rustybt-validate config show LAYER [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `LAYER` | One of: `layer_1`, `layer_2`, `layer_3`, `layer_4`, `layer_5`, or `all` |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format [table\|json]` | `table` | Output format |

**Examples:**

```bash
# Show Layer 1 (Data) tolerances
rustybt-validate config show layer_1

# Show all layers as JSON
rustybt-validate config show all --format json
```

### config defaults

Show default tolerance configuration.

```bash
rustybt-validate config defaults [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format [table\|json]` | `table` | Output format |

### config set

Set a configuration value.

```bash
rustybt-validate config set KEY VALUE
```

**Supported Keys:**

| Key | Description |
|-----|-------------|
| `editor` | Editor command with `{file}` and `{line}` placeholders |

**Examples:**

```bash
# VS Code
rustybt-validate config set editor "code -g {file}:{line}"

# Vim
rustybt-validate config set editor "vim +{line} {file}"

# Sublime Text
rustybt-validate config set editor "subl {file}:{line}"
```

### config get

Get a configuration value.

```bash
rustybt-validate config get KEY
```

**Example:**

```bash
rustybt-validate config get editor
# Output: editor = code -g {file}:{line}
```

### config list

List all configuration values.

```bash
rustybt-validate config list
```

**Output:**

```
Current configuration:
  editor = code -g {file}:{line}
```

---

## log

Log file operations.

### log validate

Validate log file schema.

```bash
rustybt-validate log validate LOG_PATH
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `LOG_PATH` | Yes | Path to log file (must exist) |

**Example:**

```bash
rustybt-validate log validate validation-sessions/20251129-143000-sma_crossover/logs/rustybt.jsonl
```

**Output (Valid):**

```
Log validation: PASSED
  Lines: 1523
  Layers: data (500), signals (250), orders (123), broker (200), portfolio (450)
```

**Output (Invalid):**

```
Log validation: FAILED
  Invalid JSON on line 45: Unexpected character
  Missing required field 'timestamp' on line 102
  Invalid layer 'unknown' on line 156
  ... and 7 more errors
```

---

## generate-fixture

Generate test data fixture.

```bash
rustybt-validate generate-fixture OUTPUT [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `OUTPUT` | Yes | Output path for fixture file |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--assets INTEGER` | `50` | Number of assets |
| `--start DATE` | `2020-01-01` | Start date |
| `--end DATE` | `2021-12-31` | End date |
| `--seed INTEGER` | `42` | Random seed for reproducibility |

**Example:**

```bash
rustybt-validate generate-fixture \
    tests/validation/fixtures/validation_data.parquet \
    --assets 10 \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --seed 123
```

---

## check-regressions

Check all sessions for potential regressions.

```bash
rustybt-validate check-regressions [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--sessions-dir PATH` | `validation-sessions` | Sessions directory |

**Example:**

```bash
rustybt-validate check-regressions
```

**Output:**

```
=== Checking for Regressions ===

Found 12 resolved bug findings

Resolved bugs:
  - FIND-001 (orders): Order fill price mismatch... [fixed 2025-11-20]
  - FIND-002 (broker): Commission calculation... [fixed 2025-11-22]
  ... and 10 more

Run 'rustybt-validate compare SESSION_ID' to check specific sessions for regressions.
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (session not found, validation failed, etc.) |

In CI mode (`status --ci`):
- `0`: Healthy (no open bugs, all critical layers validated)
- `1`: Unhealthy (open bugs or missing critical validations)

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RUSTYBT_VALIDATION_DIR` | Override default sessions directory |
| `RUSTYBT_EDITOR` | Default editor command (can be overridden via `config set editor`) |

---

## See Also

- [Getting Started Guide](getting-started.md) - Quick start tutorial
- [Investigation Guide](investigation-guide.md) - How to investigate discrepancies
- [Strategy Implementation Guide](strategy-implementation-guide.md) - Adding strategies to validation
- [Python API Reference](python-api-reference.md) - Programmatic access
