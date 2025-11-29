# Epic 5: Investigation & Classification Workflow

**Goal:** Enable systematic investigation and classification of discrepancies as BUG or DESIGN with full traceability.

**Architecture References:**
- Finding Classification Workflow (Architecture Pattern 4)
- Data Models (Architecture pg 359-402)
- CLI Interface (Architecture pg 435-452)

**Value:** Every discrepancy is investigated, classified, and either fixed or documented.

**FRs Covered:** FR41-FR54 (Investigation & Classification Workflow - 14 FRs)

---

## Story 5.1: Implement Discrepancy Presentation Interface

As a developer,
I want discrepancies presented clearly for investigation,
So that I can efficiently analyze and classify each finding.

**Acceptance Criteria:**

**Given** a session with discrepancies
**When** investigation interface is invoked
**Then** CLI presents findings clearly:

**investigate command:**
```bash
rustybt-validate investigate <session_id>
#
# === Finding FIND-001 (1/5 unclassified) ===
#
# Layer: orders
# Event: order_quantity_mismatch
# Timestamp: 2020-03-15T09:30:00
# Asset: AAPL
#
# rustybt value: 100.0
# Backtrader value: 99.0
# Difference: 1.0 (1%)
# Tolerance: 0 (exact match required)
#
# Context:
#   Previous bar: 2020-03-15T09:29:00
#   Signal: buy_signal = True
#   Order type: MARKET
#
# Actions:
#   [b] Classify as BUG (requires fix)
#   [d] Classify as DESIGN (intentional difference)
#   [s] Skip (investigate later)
#   [v] View source code locations
#   [c] View comparison context
#   [q] Quit investigation
#
# Enter action:
```

**And** finding navigation:
```bash
rustybt-validate investigate <session_id> --finding FIND-003
# Jump directly to specific finding
```

**And** layer filtering:
```bash
rustybt-validate investigate <session_id> --layer orders
# Only show findings from orders layer
```

**And** status filtering:
```bash
rustybt-validate investigate <session_id> --unclassified
# Only show unclassified findings
```

**Prerequisites:** Story 4.8 (comparison generates findings)

**Technical Notes:**
- Use Click.prompt for interactive input
- Provide context (previous/next bars) for debugging
- Show tolerance configuration for reference
- Support keyboard shortcuts for efficiency

---

## Story 5.2: Implement Source Code Linking

As a developer,
I want findings linked to relevant source code,
So that I can investigate the root cause efficiently.

**Acceptance Criteria:**

**Given** a finding being investigated
**When** source code linking is requested
**Then** relevant code locations are identified:

**locate_source() function:**
```python
def locate_source(finding: Finding, framework: str) -> list[SourceLocation]:
    """Locate relevant source code for finding."""
    locations = []

    # Map layer to source modules
    layer_modules = {
        "data": ["rustybt/data/", "zipline/data/"],
        "signals": ["rustybt/algorithm.py", "rustybt/signals/"],
        "orders": ["rustybt/finance/order.py", "rustybt/finance/blotter.py"],
        "broker": ["rustybt/finance/broker.py", "rustybt/finance/commission.py"],
        "portfolio": ["rustybt/finance/portfolio.py", "rustybt/finance/returns.py"],
    }

    # Search for event-related functions
    for module_pattern in layer_modules.get(finding.layer, []):
        matches = grep_for_event(module_pattern, finding.event)
        locations.extend(matches)

    return locations
```

**And** CLI view source command:
```bash
# In investigation mode, press 'v':
#
# Source code locations for FIND-001:
#
# rustybt locations:
#   1. rustybt/finance/order.py:142 - order_quantity calculation
#   2. rustybt/finance/blotter.py:89 - create_order()
#
# Backtrader locations (reference):
#   1. backtrader/order.py:234 - Order.__init__
#   2. backtrader/broker.py:456 - submit()
#
# Open location? [1-4 or n to skip]:
```

**And** support for opening files in editor:
```bash
rustybt-validate config set editor "code -g {file}:{line}"
# Opens file in VS Code at specific line
```

**Prerequisites:** Story 5.1 (investigation interface)

**Technical Notes:**
- Use grep/ripgrep for code search
- Support configurable editor command
- Cache source locations for repeated queries
- Include Backtrader source for reference

---

## Story 5.3: Implement BUG Classification Workflow

As a developer,
I want to classify findings as BUG with required rationale,
So that bugs are properly documented and tracked for fixing.

**Acceptance Criteria:**

**Given** a finding requiring classification
**When** BUG classification is selected
**Then** workflow captures required information:

**CLI workflow:**
```bash
# Press 'b' to classify as BUG:
#
# === Classify as BUG ===
#
# Rationale (required - explain why this is a bug):
# > Order quantity calculation doesn't account for fractional shares
#
# Affected component(s):
# > rustybt/finance/order.py
#
# Severity:
#   [1] Critical - incorrect results
#   [2] Major - significant deviation
#   [3] Minor - small deviation
# > 2
#
# Suggested fix (optional):
# > Add round() to quantity calculation in create_order()
#
# === BUG Classification Saved ===
# Finding FIND-001 classified as BUG (Major)
# Next: Create fix in rustybt, then use 'rustybt-validate verify <finding_id>'
```

**And** Finding model updated:
```python
finding.classification = "BUG"
finding.rationale = "Order quantity calculation doesn't account for fractional shares"
finding.severity = "Major"
finding.affected_components = ["rustybt/finance/order.py"]
finding.suggested_fix = "Add round() to quantity calculation"
finding.investigated_by = "smirk"
finding.investigated_at = datetime.now()
```

**And** validation requires:
- Rationale (non-empty string)
- Affected component (at least one)
- Severity level

**Prerequisites:** Story 5.1 (investigation interface)

**Technical Notes:**
- Store all BUG metadata in findings.yaml
- Rationale required to prevent lazy classification
- Severity helps prioritize fixes
- Suggested fix is optional but helpful

---

## Story 5.4: Implement DESIGN Classification Workflow

As a developer,
I want to classify findings as DESIGN with documentation,
So that intentional differences are properly documented for users.

**Acceptance Criteria:**

**Given** a finding requiring classification
**When** DESIGN classification is selected
**Then** workflow captures required information:

**CLI workflow:**
```bash
# Press 'd' to classify as DESIGN:
#
# === Classify as DESIGN ===
#
# Rationale (required - explain why this is intentional):
# > rustybt uses Wilder's smoothing for RSI, Backtrader uses EMA smoothing.
# > This is a valid design choice with industry precedent.
#
# Which framework is correct? (both may be valid):
#   [r] rustybt approach is preferred
#   [b] Backtrader approach is preferred
#   [e] Either approach is valid
# > e
#
# User impact:
# > Users may see ~0.5% difference in RSI values. No functional impact on signal timing.
#
# Documentation reference (will be created if doesn't exist):
# > docs/validation/design-differences.md#rsi-calculation
#
# === DESIGN Classification Saved ===
# Finding FIND-002 classified as DESIGN
# Documentation stub created at docs/validation/design-differences.md
```

**And** Finding model updated:
```python
finding.classification = "DESIGN"
finding.rationale = "rustybt uses Wilder's smoothing for RSI..."
finding.design_choice = "either_valid"
finding.user_impact = "Users may see ~0.5% difference..."
finding.documentation_ref = "docs/validation/design-differences.md#rsi-calculation"
finding.investigated_by = "smirk"
finding.investigated_at = datetime.now()
```

**And** auto-generates documentation stub if doesn't exist

**Prerequisites:** Story 5.1 (investigation interface)

**Technical Notes:**
- DESIGN differences must be documented for users
- Auto-create docs/validation/design-differences.md
- Include anchor links for specific findings
- User impact helps users understand practical implications

---

## Story 5.5: Implement Bug Fix Verification

As a developer,
I want to verify that bug fixes resolve discrepancies,
So that fixes are validated before marking findings as resolved.

**Acceptance Criteria:**

**Given** a BUG-classified finding that has been fixed
**When** verification is invoked
**Then** the fix is validated:

**verify command:**
```bash
rustybt-validate verify FIND-001
#
# === Verifying Fix for FIND-001 ===
#
# Original discrepancy:
#   Layer: orders
#   Event: order_quantity_mismatch
#   rustybt: 100.0, Backtrader: 99.0
#
# Re-running strategy execution...
# ✓ rustybt executed successfully
# ✓ Backtrader executed successfully
#
# Re-running layer comparison...
# ✓ Order quantities now match
#
# === Fix Verified ===
# FIND-001 marked as resolved
# Regression test created: tests/validation/regression/test_find_001.py
```

**And** verification fails if discrepancy persists:
```bash
# ✗ Verification failed
# Discrepancy still present:
#   rustybt: 100.0, Backtrader: 99.0
#
# Fix not complete. Finding remains open.
```

**And** verification updates finding:
```python
finding.resolved = True
finding.resolved_at = datetime.now()
finding.regression_test = "tests/validation/regression/test_find_001.py"
```

**Prerequisites:** Story 5.3 (BUG classification), Story 4.8 (comparison)

**Technical Notes:**
- Re-executes strategy with same parameters
- Re-runs comparison for affected layer only
- Must pass to mark as resolved
- Creates regression test automatically

---

## Story 5.6: Implement Regression Test Generation

As a developer,
I want regression tests auto-generated for fixed bugs,
So that bugs don't reappear in future development.

**Acceptance Criteria:**

**Given** a verified bug fix
**When** regression test generation is triggered
**Then** a pytest test is created:

**Generated test:**
```python
# tests/validation/regression/test_find_001.py
"""
Regression test for FIND-001: Order quantity mismatch

Original finding:
- Layer: orders
- Event: order_quantity_mismatch
- rustybt: 100.0, Backtrader: 99.0

Fixed: 2025-11-24
Fix: Added round() to quantity calculation in rustybt/finance/order.py
"""
import pytest
from rustybt.validation import compare_layer, load_tolerances

@pytest.mark.regression
@pytest.mark.layer_3_orders
def test_find_001_order_quantity(sma_crossover_logs):
    """Verify order quantities match after fix for FIND-001."""
    tolerances = load_tolerances("layer_orders")

    discrepancies = compare_layer(
        "orders",
        sma_crossover_logs["rustybt"],
        sma_crossover_logs["backtrader"],
        tolerances
    )

    # Specific check for the fixed issue
    quantity_mismatches = [
        d for d in discrepancies
        if d.event == "order_quantity_mismatch"
    ]

    assert len(quantity_mismatches) == 0, (
        f"Regression: Order quantity mismatch detected. "
        f"Original bug FIND-001 may have reappeared."
    )
```

**And** regression test includes:
- Reference to original finding ID
- Original discrepancy details
- Fix date and description
- Specific assertion for the fixed issue

**And** regression tests run in CI:
```bash
pytest tests/validation/regression/ -v
```

**Prerequisites:** Story 5.5 (fix verification)

**Technical Notes:**
- Use pytest markers for categorization
- Include original finding context in docstring
- Generate meaningful test name from finding ID
- Store generated tests in regression/ subdirectory

---

## Story 5.7: Implement Regression Detection

As a developer,
I want automatic detection when fixed bugs reappear,
So that regressions are caught immediately.

**Acceptance Criteria:**

**Given** existing regression tests
**When** validation is run
**Then** regressions are detected and reported:

**Regression detection:**
```python
def detect_regressions(
    session: Session,
    discrepancies: list[Discrepancy]
) -> list[Regression]:
    """Check if any discrepancies match previously fixed bugs."""
    regressions = []

    # Load all resolved BUG findings
    resolved_bugs = load_resolved_bugs()

    for discrepancy in discrepancies:
        for bug in resolved_bugs:
            if matches_finding(discrepancy, bug):
                regressions.append(Regression(
                    original_finding=bug.id,
                    current_discrepancy=discrepancy,
                    fixed_at=bug.resolved_at,
                    regression_detected_at=datetime.now()
                ))

    return regressions
```

**And** CLI reports regressions prominently:
```bash
rustybt-validate compare <session_id>
#
# ⚠️ REGRESSION DETECTED ⚠️
#
# Finding FIND-001 (fixed 2025-11-24) has reappeared!
#   Layer: orders
#   Event: order_quantity_mismatch
#   Original fix: Added round() to quantity calculation
#
# This may indicate the fix was reverted or a new code path introduced the bug.
#
# Action required: Investigate and fix before proceeding.
```

**And** regressions block session completion

**Prerequisites:** Story 5.6 (regression tests)

**Technical Notes:**
- Compare discrepancies against resolved findings database
- Match by layer + event + similar values
- Regressions are critical - require immediate attention
- Block session completion until resolved

---
