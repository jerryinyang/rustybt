# Examples & Recipes Cookbook

This cookbook provides complete, runnable examples for common validation framework use cases. Each recipe follows the pattern: **Problem** → **Solution** → **Explanation**.

---

## Recipe: Validating a New Strategy from Scratch

**Problem:** You have a new trading strategy implemented in rustybt and want to validate it against the equivalent Backtrader implementation.

**Solution:**

### Step 1: Create the Strategy Implementations

**rustybt Strategy (`strategies/sma_crossover_rustybt.py`):**
```python
"""SMA Crossover strategy for rustybt."""
from rustybt import Strategy, order_target_percent
from rustybt.indicators import SMA

class SMACrossover(Strategy):
    params = {
        "fast_period": 10,
        "slow_period": 30,
    }

    def initialize(self):
        self.fast_sma = SMA(self.data.close, period=self.params["fast_period"])
        self.slow_sma = SMA(self.data.close, period=self.params["slow_period"])
        self.position_size = 0

    def next(self):
        if self.fast_sma[-1] > self.slow_sma[-1] and self.position_size <= 0:
            order_target_percent(self.data, 1.0)
            self.position_size = 1
        elif self.fast_sma[-1] < self.slow_sma[-1] and self.position_size >= 0:
            order_target_percent(self.data, 0.0)
            self.position_size = 0
```

**Backtrader Strategy (`strategies/sma_crossover_backtrader.py`):**
```python
"""SMA Crossover strategy for Backtrader."""
import backtrader as bt

class SMACrossover(bt.Strategy):
    params = (
        ("fast_period", 10),
        ("slow_period", 30),
    )

    def __init__(self):
        self.fast_sma = bt.indicators.SMA(
            self.data.close, period=self.params.fast_period
        )
        self.slow_sma = bt.indicators.SMA(
            self.data.close, period=self.params.slow_period
        )

    def next(self):
        if self.fast_sma[0] > self.slow_sma[0] and not self.position:
            self.order_target_percent(target=1.0)
        elif self.fast_sma[0] < self.slow_sma[0] and self.position:
            self.order_target_percent(target=0.0)
```

### Step 2: Create a Validation Session

```bash
# Create a new validation session
rustybt-validate session create sma_crossover

# Expected output:
# ✓ Created session: 20251124-143000-sma_crossover
# Session ID: 20251124-143000-sma_crossover
# Stage: CREATED
```

### Step 3: Run Both Frameworks

```bash
# Run strategies and generate logs
rustybt-validate run sma_crossover \
    --rustybt-strategy strategies/sma_crossover_rustybt.py \
    --backtrader-strategy strategies/sma_crossover_backtrader.py \
    --data data/AAPL_2023.csv \
    --start-date 2023-01-01 \
    --end-date 2023-12-31

# Expected output:
# ✓ Running rustybt strategy...
# ✓ Running Backtrader strategy...
# ✓ Log files generated
# Stage: EXECUTION -> COMPARISON
```

### Step 4: Compare Results

```bash
# Compare logs across all 5 layers
rustybt-validate compare 20251124-143000-sma_crossover

# Expected output:
# Comparing layer 1 (Data Handling)... ✓ 0 discrepancies
# Comparing layer 2 (Signal Computation)... ✓ 0 discrepancies
# Comparing layer 3 (Order Lifecycle)... ✓ 0 discrepancies
# Comparing layer 4 (Broker Transaction)... ✓ 0 discrepancies
# Comparing layer 5 (Portfolio Returns)... ✓ 0 discrepancies
# Stage: COMPARISON -> INVESTIGATION
```

### Step 5: Generate Report

```bash
# Generate validation report
rustybt-validate report 20251124-143000-sma_crossover --format markdown

# Expected output:
# ✓ Report generated: .validation/sessions/20251124-143000-sma_crossover/report.md
```

**Explanation:** This recipe walks through the complete validation workflow:
1. Strategy implementations must exist in both frameworks
2. Sessions track the validation state
3. Execution runs both strategies with identical data
4. Comparison identifies discrepancies across all layers
5. Reports summarize findings for stakeholders

---

## Recipe: Resuming an Interrupted Validation Session

**Problem:** Your validation session was interrupted (computer restart, network issue, etc.) and you need to continue from where you left off.

**Solution:**

### Step 1: Find Interrupted Sessions

```bash
# List all sessions with IN_PROGRESS status
rustybt-validate session list --status in-progress

# Expected output:
# Sessions (IN_PROGRESS):
# ┌─────────────────────────────────────┬──────────────┬───────────────┬─────────────────────┐
# │ Session ID                          │ Strategy     │ Stage         │ Created             │
# ├─────────────────────────────────────┼──────────────┼───────────────┼─────────────────────┤
# │ 20251124-093000-mean_reversion     │ mean_reversion│ COMPARISON    │ 2024-11-24 09:30:00 │
# │ 20251124-143000-sma_crossover      │ sma_crossover│ INVESTIGATION │ 2024-11-24 14:30:00 │
# └─────────────────────────────────────┴──────────────┴───────────────┴─────────────────────┘
```

### Step 2: Check Session Details

```bash
# See what stage the session is at
rustybt-validate session show 20251124-143000-sma_crossover

# Expected output:
# Session: 20251124-143000-sma_crossover
# Strategy: sma_crossover
# Stage: INVESTIGATION
# Status: IN_PROGRESS
# Created: 2024-11-24T14:30:00
# Last Activity: 2024-11-24T15:45:00
#
# Progress:
#   ✓ CREATED
#   ✓ EXECUTION
#   ✓ COMPARISON
#   → INVESTIGATION (current)
#   ○ VERIFICATION
#   ○ COMPLETED
```

### Step 3: Resume the Session

```bash
# Resume from where you left off
rustybt-validate session resume 20251124-143000-sma_crossover

# Expected output:
# ✓ Resumed session: 20251124-143000-sma_crossover
# Current stage: INVESTIGATION
# Pending findings: 3
```

### Step 4: Continue Work

```bash
# Continue with investigation
rustybt-validate investigate 20251124-143000-sma_crossover

# View pending findings
rustybt-validate session findings 20251124-143000-sma_crossover --status pending
```

**Python API Approach:**
```python
from rustybt.validation import SessionManager
from pathlib import Path

manager = SessionManager(Path(".validation"))

# List in-progress sessions
sessions = manager.list_sessions(status="IN_PROGRESS")
for session in sessions:
    print(f"{session.id}: Stage={session.stage}, Strategy={session.strategy}")

# Resume specific session
session = manager.get_session("20251124-143000-sma_crossover")
print(f"Resuming at stage: {session.stage}")

# Session state is automatically preserved:
# - All previous findings
# - Activity log
# - Log files
# - Current stage
```

**Explanation:** Session state is persisted to disk after every operation. When you resume:
- All findings from previous work are preserved
- The activity log shows what was done before
- You continue from the exact stage where work stopped
- Log files and comparisons don't need to be re-run

---

## Recipe: Investigating a Specific Layer's Discrepancies

**Problem:** You have discrepancies in a specific layer (e.g., Order Lifecycle) and want to investigate them in detail.

**Solution:**

### Step 1: Filter Findings by Layer

```bash
# View findings for layer 3 (Order Lifecycle) only
rustybt-validate session findings 20251124-143000-sma_crossover --layer 3

# Expected output:
# Layer 3 (Order Lifecycle) Findings:
# ┌────────────────────┬────────────────────┬──────────────────────┬──────────┐
# │ Finding ID         │ Event              │ Timestamp            │ Status   │
# ├────────────────────┼────────────────────┼──────────────────────┼──────────┤
# │ L3-001             │ order_submitted    │ 2024-03-15T09:31:00  │ PENDING  │
# │ L3-002             │ order_filled       │ 2024-03-15T09:31:05  │ PENDING  │
# │ L3-003             │ order_submitted    │ 2024-06-22T14:45:00  │ PENDING  │
# └────────────────────┴────────────────────┴──────────────────────┴──────────┘
```

### Step 2: Drill Into a Specific Finding

```bash
# Investigate a specific finding
rustybt-validate investigate 20251124-143000-sma_crossover --finding L3-001

# Expected output:
# Finding: L3-001
# Layer: 3 (Order Lifecycle)
# Event: order_submitted
# Timestamp: 2024-03-15T09:31:00
#
# rustybt:
#   order_id: "ORD-001"
#   symbol: "AAPL"
#   side: "BUY"
#   quantity: 100
#   order_type: "MARKET"
#   submitted_at: "2024-03-15T09:31:00.000"
#
# Backtrader:
#   order_id: "ORD-001"
#   symbol: "AAPL"
#   side: "BUY"
#   quantity: 100
#   order_type: "MKT"          # <-- Discrepancy here
#   submitted_at: "2024-03-15T09:31:00.000"
#
# Discrepancy: order_type differs ("MARKET" vs "MKT")
```

### Step 3: Classify the Finding

```bash
# Classify as DESIGN difference (different string representation, same behavior)
rustybt-validate investigate 20251124-143000-sma_crossover \
    --finding L3-001 \
    --classification DESIGN \
    --reason "Order type uses different string representation. MARKET=MKT semantically equivalent."

# Expected output:
# ✓ Finding L3-001 classified as DESIGN
# Reason: Order type uses different string representation. MARKET=MKT semantically equivalent.
```

### Step 4: Batch Process Similar Findings

```bash
# Classify all similar order_type findings at once
rustybt-validate investigate 20251124-143000-sma_crossover \
    --layer 3 \
    --event order_submitted \
    --classification DESIGN \
    --reason "Order type string representation differs (MARKET vs MKT)"

# Expected output:
# ✓ Classified 5 findings as DESIGN
```

**Python API Approach:**
```python
from rustybt.validation import SessionManager
from rustybt.validation.comparators import Layer3OrderComparator
from pathlib import Path

manager = SessionManager(Path(".validation"))
session = manager.get_session("20251124-143000-sma_crossover")

# Get layer 3 findings
layer3_findings = [f for f in session.findings if f.layer == 3]

# Analyze each finding
comparator = Layer3OrderComparator()
for finding in layer3_findings:
    print(f"\n{finding.id}: {finding.event}")
    print(f"  rustybt: {finding.rustybt_value}")
    print(f"  backtrader: {finding.backtrader_value}")

    # Programmatic classification
    if finding.field == "order_type":
        # Normalize and compare
        rb_type = finding.rustybt_value.upper()
        bt_type = {"MKT": "MARKET", "LMT": "LIMIT"}.get(
            finding.backtrader_value, finding.backtrader_value
        )
        if rb_type == bt_type:
            manager.classify_finding(
                session.id,
                finding.id,
                classification="DESIGN",
                reason="Equivalent order type with different string representation"
            )
```

**Explanation:** Layer-specific investigation allows you to:
- Focus on one category of discrepancies at a time
- Identify patterns (e.g., all order_type fields differ the same way)
- Batch classify similar findings
- Build a systematic understanding of framework differences

---

## Recipe: Adding a New Tolerance Configuration

**Problem:** The default tolerances are too strict for your use case, and you need to configure custom tolerances for your comparison.

**Solution:**

### Step 1: View Default Tolerances

```bash
# See current tolerance configuration
rustybt-validate config show

# Expected output:
# Tolerance Configuration:
#
# Layer 1 (Data Handling):
#   timestamp_window_ms: 1
#   price_decimal_places: 4
#   volume_tolerance_pct: 0.001
#   bar_count_tolerance: 0
#
# Layer 2 (Signal Computation):
#   indicator_decimal_places: 4
#   signal_tolerance_pct: 0.0001
#   signal_exact_match: true
#   ...
```

### Step 2: Create Custom Tolerance File

Create `tolerances.yaml` in your project:

```yaml
# Custom tolerances for high-frequency strategy validation
# Relaxed tolerances for microsecond timing and tick-level prices

layer_1_data:
  # Allow 100ms timestamp difference (HFT timing)
  timestamp_window_ms: 100
  # Match to 2 decimal places (tick-level)
  price_decimal_places: 2
  # Allow 1% volume difference
  volume_tolerance_pct: 0.01
  # Exact bar count match
  bar_count_tolerance: 0

layer_2_signals:
  # Indicator values to 2 decimal places
  indicator_decimal_places: 2
  # 0.1% signal tolerance
  signal_tolerance_pct: 0.001
  # Signals don't need exact match
  signal_exact_match: false
  # 100ms signal timing window
  signal_timestamp_window_ms: 100

layer_3_orders:
  # 100ms order timing window
  order_timestamp_window_ms: 100
  # Fill price to 2 decimal places
  fill_price_decimal_places: 2
  # 0.01% quantity tolerance
  quantity_tolerance_pct: 0.0001
  # Order IDs won't match
  order_id_exact_match: false

layer_4_broker:
  # 100ms transaction timing
  transaction_timestamp_window_ms: 100
  # Commission to cents
  commission_decimal_places: 2
  # 0.1% slippage tolerance
  slippage_tolerance_pct: 0.001
  # Cash to cents
  cash_decimal_places: 2

layer_5_portfolio:
  # Portfolio value to cents
  portfolio_value_decimal_places: 2
  # 0.01% returns tolerance
  returns_tolerance_pct: 0.0001
  # Sharpe to 2 decimal places
  sharpe_decimal_places: 2
  # 0.01% drawdown tolerance
  drawdown_tolerance_pct: 0.0001
```

### Step 3: Apply Custom Tolerances

```bash
# Use custom tolerances for comparison
rustybt-validate compare 20251124-143000-sma_crossover --config tolerances.yaml

# Expected output:
# Using custom tolerances from: tolerances.yaml
# Comparing layer 1 (Data Handling)... ✓ 0 discrepancies
# ...
```

### Step 4: Set Tolerances as Default

```bash
# Set as project default
rustybt-validate config set --file tolerances.yaml

# Or set individual values
rustybt-validate config set layer_1_price_decimal_places 2
```

**Python API Approach:**
```python
from rustybt.validation.tolerance import ToleranceConfig
from pathlib import Path

# Load from YAML
config = ToleranceConfig.load_from_yaml(Path("tolerances.yaml"))

# Or create programmatically
config = ToleranceConfig()
relaxed = config.with_overrides(
    layer_1_price_decimal_places=2,
    layer_1_timestamp_window_ms=100,
    layer_2_signal_exact_match=False,
)

# View calculated tolerances
print(f"Price tolerance: {relaxed.layer_1.price_tolerance}")  # 0.01
print(f"Signal match required: {relaxed.layer_2.signal_exact_match}")  # False

# Save for reuse
with open("tolerances.yaml", "w") as f:
    import yaml
    yaml.dump(relaxed.to_dict(), f)
```

**Explanation:** Tolerance configuration allows you to:
- Account for legitimate precision differences between frameworks
- Handle timing differences in execution environments
- Focus on semantic equivalence rather than exact byte-matching
- Document acceptable differences for your specific use case

---

## Recipe: Generating a Validation Report for Stakeholders

**Problem:** You need to generate a report summarizing validation results for your team or management.

**Solution:**

### Step 1: Generate Markdown Report

```bash
# Generate comprehensive markdown report
rustybt-validate report 20251124-143000-sma_crossover --format markdown

# Expected output:
# ✓ Report generated: .validation/sessions/20251124-143000-sma_crossover/report.md
```

**Sample Report Output:**
```markdown
# Validation Report: sma_crossover

**Session ID:** 20251124-143000-sma_crossover
**Generated:** 2024-11-24T16:00:00
**Status:** COMPLETED

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Findings | 12 |
| Bugs Identified | 2 |
| Design Differences | 10 |
| Validation Status | PASSED (with notes) |

## Layer Summary

| Layer | Findings | Bugs | Design | Pass |
|-------|----------|------|--------|------|
| 1 - Data | 0 | 0 | 0 | ✓ |
| 2 - Signals | 0 | 0 | 0 | ✓ |
| 3 - Orders | 5 | 0 | 5 | ✓ |
| 4 - Broker | 5 | 2 | 3 | ✗ |
| 5 - Portfolio | 2 | 0 | 2 | ✓ |

## Bugs Requiring Action

### BUG-001: Commission Calculation Difference
- **Layer:** 4 (Broker)
- **Severity:** Medium
- **Description:** Commission calculated as $1.50 in rustybt vs $1.00 in Backtrader
- **Impact:** Affects PnL calculations by ~0.5%
- **Recommended Action:** Review commission model implementation

...
```

### Step 2: Generate JSON for Programmatic Use

```bash
# Generate JSON report for CI/CD integration
rustybt-validate report 20251124-143000-sma_crossover --format json > report.json

# Use in scripts
cat report.json | jq '.summary.bugs_count'
```

### Step 3: Generate Summary Dashboard

```bash
# Quick ASCII dashboard
rustybt-validate status 20251124-143000-sma_crossover

# Expected output:
# ╔════════════════════════════════════════════════════════════════╗
# ║          Validation Status: sma_crossover                      ║
# ╠════════════════════════════════════════════════════════════════╣
# ║  Layer 1 - Data Handling      ████████████████████████ ✓       ║
# ║  Layer 2 - Signal Computation ████████████████████████ ✓       ║
# ║  Layer 3 - Order Lifecycle    ██████████████████░░░░░░ ✓       ║
# ║  Layer 4 - Broker Transaction ████████████░░░░░░░░░░░░ ✗       ║
# ║  Layer 5 - Portfolio Returns  ████████████████████████ ✓       ║
# ╠════════════════════════════════════════════════════════════════╣
# ║  Total: 12 findings (2 bugs, 10 design)                        ║
# ╚════════════════════════════════════════════════════════════════╝
```

### Step 4: Generate Layer-Specific Report

```bash
# Detailed report for a specific layer
rustybt-validate report 20251124-143000-sma_crossover --layer 4 --format markdown

# Strategy-specific reports
rustybt-validate report --strategy sma_crossover --all-sessions
```

**Python API Approach:**
```python
from rustybt.validation import SessionManager
from rustybt.validation.reporting import (
    ReportGenerator,
    StatusDashboard,
    LayerReportGenerator,
)
from pathlib import Path

manager = SessionManager(Path(".validation"))
session = manager.get_session("20251124-143000-sma_crossover")

# Generate comprehensive report
generator = ReportGenerator(session)
markdown_report = generator.generate_markdown()
json_report = generator.generate_json()

# Save reports
Path("validation_report.md").write_text(markdown_report)
Path("validation_report.json").write_text(json_report)

# Generate dashboard
dashboard = StatusDashboard(session)
print(dashboard.render())

# Layer-specific report
layer_gen = LayerReportGenerator(session, layer=4)
layer_report = layer_gen.generate()
print(layer_report)
```

**Explanation:** Reports serve different audiences:
- **Markdown:** Human-readable for team review
- **JSON:** Machine-readable for CI/CD and dashboards
- **ASCII Dashboard:** Quick terminal overview
- **Layer-specific:** Deep-dive into specific areas

---

## Recipe: Running Validation in CI/CD Pipeline

**Problem:** You want to automatically validate rustybt against Backtrader on every commit or pull request.

**Solution:**

### GitHub Actions Workflow

Create `.github/workflows/validation.yml`:

```yaml
name: Validation Framework CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install rustybt backtrader pytest

      - name: Run validation for all strategies
        run: |
          # Create session for each strategy
          for strategy in strategies/*.py; do
            name=$(basename "$strategy" .py)
            rustybt-validate session create "$name" --force
            rustybt-validate run "$name" --config ci-tolerances.yaml
            rustybt-validate compare "$name"
          done

      - name: Check for bugs
        run: |
          # Fail CI if any bugs found
          rustybt-validate check-regressions --fail-on-bugs

      - name: Generate reports
        run: |
          mkdir -p reports
          rustybt-validate report --all --format markdown > reports/validation.md
          rustybt-validate report --all --format json > reports/validation.json

      - name: Upload reports
        uses: actions/upload-artifact@v4
        with:
          name: validation-reports
          path: reports/
          retention-days: 30

      - name: Post status comment
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('reports/validation.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: report
            });
```

### pytest Integration

Create `tests/test_validation.py`:

```python
"""pytest integration for validation framework."""
import pytest
from pathlib import Path
from rustybt.validation import SessionManager
from rustybt.validation.comparators import (
    Layer1DataComparator,
    Layer2SignalComparator,
    Layer3OrderComparator,
    Layer4BrokerComparator,
    Layer5PortfolioComparator,
)


@pytest.fixture
def session_manager():
    """Provide session manager for tests."""
    return SessionManager(Path(".validation"))


@pytest.fixture
def validation_session(session_manager):
    """Create or get validation session."""
    session = session_manager.create_session("sma_crossover", force=True)
    yield session
    # Cleanup after test
    session_manager.delete_session(session.id)


class TestValidation:
    """Validation test suite."""

    def test_layer1_data_handling(self, validation_session):
        """Verify data layer has no discrepancies."""
        comparator = Layer1DataComparator()
        result = comparator.compare(
            Path(".validation/logs/rustybt.jsonl"),
            Path(".validation/logs/backtrader.jsonl"),
        )

        assert result.passed, f"Layer 1 failed: {len(result.discrepancies)} issues"
        assert len(result.discrepancies) == 0

    def test_layer2_signals(self, validation_session):
        """Verify signal computation matches."""
        comparator = Layer2SignalComparator()
        result = comparator.compare(
            Path(".validation/logs/rustybt.jsonl"),
            Path(".validation/logs/backtrader.jsonl"),
        )

        assert result.passed, f"Layer 2 failed: {result.discrepancies}"

    def test_no_bugs_in_session(self, session_manager, validation_session):
        """Verify no bugs found in validation."""
        findings = session_manager.get_findings(validation_session.id)
        bugs = [f for f in findings if f.classification == "BUG"]

        assert len(bugs) == 0, f"Found {len(bugs)} bugs: {bugs}"

    @pytest.mark.parametrize("layer", [1, 2, 3, 4, 5])
    def test_all_layers_pass(self, validation_session, layer):
        """Parameterized test for all layers."""
        comparators = {
            1: Layer1DataComparator,
            2: Layer2SignalComparator,
            3: Layer3OrderComparator,
            4: Layer4BrokerComparator,
            5: Layer5PortfolioComparator,
        }

        comparator = comparators[layer]()
        result = comparator.compare(
            Path(".validation/logs/rustybt.jsonl"),
            Path(".validation/logs/backtrader.jsonl"),
        )

        assert result.passed, f"Layer {layer} failed validation"
```

### Exit Codes for CI

```bash
# Exit code reference:
# 0 - All validations passed
# 1 - Bugs found (validation failed)
# 2 - Session error (could not run validation)

# Check for regressions with appropriate exit code
rustybt-validate check-regressions --fail-on-bugs
echo "Exit code: $?"

# In CI script:
if ! rustybt-validate check-regressions --fail-on-bugs; then
    echo "Validation failed - bugs detected"
    exit 1
fi
```

**Explanation:** CI/CD integration enables:
- Automatic validation on every code change
- Early detection of behavioral regressions
- Artifact storage for debugging
- PR comments with validation status
- pytest integration for standard test workflows

---

## Recipe: Comparing Results Across rustybt Versions

**Problem:** You want to detect if a new rustybt version introduces regressions in behavior compared to the previous version.

**Solution:**

### Step 1: Run Validation on Old Version

```bash
# Checkout old version
git checkout v1.0.0

# Create virtual environment for old version
python -m venv .venv-v1.0.0
source .venv-v1.0.0/bin/activate
pip install -e .

# Run validation
rustybt-validate session create sma_crossover --tag "v1.0.0"
rustybt-validate run sma_crossover
rustybt-validate compare sma_crossover

# Save session ID
OLD_SESSION=$(rustybt-validate session list --strategy sma_crossover --tag v1.0.0 --quiet)

deactivate
```

### Step 2: Run Validation on New Version

```bash
# Checkout new version
git checkout v1.1.0

# Create virtual environment for new version
python -m venv .venv-v1.1.0
source .venv-v1.1.0/bin/activate
pip install -e .

# Run validation
rustybt-validate session create sma_crossover --tag "v1.1.0"
rustybt-validate run sma_crossover
rustybt-validate compare sma_crossover

NEW_SESSION=$(rustybt-validate session list --strategy sma_crossover --tag v1.1.0 --quiet)

deactivate
```

### Step 3: Compare Sessions

```bash
# Activate main environment
source .venv/bin/activate

# Compare findings between versions
rustybt-validate check-regressions \
    --baseline "$OLD_SESSION" \
    --current "$NEW_SESSION"

# Expected output:
# Regression Check: v1.0.0 → v1.1.0
#
# New findings in v1.1.0:
# ┌────────────────────┬────────────────────┬──────────────────────┐
# │ Finding ID         │ Layer              │ Description          │
# ├────────────────────┼────────────────────┼──────────────────────┤
# │ L4-005             │ Broker             │ New slippage calc    │
# └────────────────────┴────────────────────┴──────────────────────┘
#
# Resolved findings from v1.0.0:
# ┌────────────────────┬────────────────────┬──────────────────────┐
# │ Finding ID         │ Layer              │ Description          │
# ├────────────────────┼────────────────────┼──────────────────────┤
# │ L3-002             │ Orders             │ Order ID format      │
# └────────────────────┴────────────────────┴──────────────────────┘
#
# Summary: 1 new finding, 1 resolved finding
```

### Step 4: Generate Comparison Report

```bash
# Generate diff report
rustybt-validate report \
    --compare "$OLD_SESSION" "$NEW_SESSION" \
    --format markdown \
    > version_comparison.md
```

**Python API Approach:**
```python
from rustybt.validation import SessionManager
from rustybt.validation.regression_detection import RegressionDetector
from pathlib import Path

manager = SessionManager(Path(".validation"))

# Get sessions for both versions
old_session = manager.get_session("20251120-100000-sma_crossover-v1.0.0")
new_session = manager.get_session("20251124-100000-sma_crossover-v1.1.0")

# Detect regressions
detector = RegressionDetector(manager)
result = detector.compare_sessions(
    baseline_id=old_session.id,
    current_id=new_session.id,
)

# Analyze results
print(f"New findings: {len(result.new_findings)}")
print(f"Resolved findings: {len(result.resolved_findings)}")
print(f"Unchanged findings: {len(result.unchanged_findings)}")

# Check for regressions
if result.has_regressions:
    print("\nREGRESSION DETECTED!")
    for finding in result.new_findings:
        if finding.classification == "BUG":
            print(f"  - {finding.id}: {finding.description}")

# Access version metadata
print(f"\nBaseline version: {old_session.metadata.get('tag', 'unknown')}")
print(f"Current version: {new_session.metadata.get('tag', 'unknown')}")
```

**Explanation:** Version comparison helps:
- Detect behavioral regressions before release
- Track which findings are fixed in new versions
- Maintain behavioral consistency across releases
- Document intentional changes (DESIGN differences)

---

## Quick Reference

### Common Command Patterns

```bash
# Session lifecycle
rustybt-validate session create <strategy>
rustybt-validate run <strategy>
rustybt-validate compare <session_id>
rustybt-validate investigate <session_id>
rustybt-validate verify <session_id>
rustybt-validate report <session_id>

# Session management
rustybt-validate session list
rustybt-validate session show <session_id>
rustybt-validate session resume <session_id>
rustybt-validate session delete <session_id>

# Investigation shortcuts
rustybt-validate investigate <session_id> --layer 3
rustybt-validate investigate <session_id> --finding L3-001 --classification BUG

# Reports
rustybt-validate report <session_id> --format markdown
rustybt-validate status <session_id>
rustybt-validate progress

# Configuration
rustybt-validate config show
rustybt-validate config set <key> <value>
```

### Python API Quick Start

```python
from rustybt.validation import SessionManager
from pathlib import Path

manager = SessionManager(Path(".validation"))

# Create and run
session = manager.create_session("my_strategy")
# ... run strategies ...
session = manager.advance_stage(session.id, "COMPARISON")

# Compare
from rustybt.validation.comparators import Layer1DataComparator
comparator = Layer1DataComparator()
result = comparator.compare(rb_log, bt_log)

# Report
from rustybt.validation.reporting import ReportGenerator
report = ReportGenerator(session).generate_markdown()
```

---

## See Also

- [Getting Started](getting-started.md) - Initial setup tutorial
- [CLI Reference](cli-reference.md) - Complete command documentation
- [Python API Reference](python-api-reference.md) - Programmatic usage
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
