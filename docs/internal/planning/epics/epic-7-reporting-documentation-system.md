# Epic 7: Reporting & Documentation System

**Goal:** Provide comprehensive reporting and documentation generation for validation results.

**Architecture References:**
- Reporting (Architecture pg 442-448)
- CLI Interface (Architecture pg 435-452)

**Value:** Clear visibility into validation status and comprehensive documentation for users.

**FRs Covered:** FR60-FR73 (Reporting & Documentation + Data/Config - 14 FRs)

---

## Story 7.1: Implement Session Report Generator

As a developer,
I want detailed reports per session,
So that validation results are clearly documented.

**Acceptance Criteria:**

**Given** a completed or in-progress session
**When** report generation is invoked
**Then** a markdown report is generated:

**Report structure:**
```markdown
# Validation Session Report

**Session ID:** 20251123-230000-sma_crossover
**Strategy:** SMA Crossover
**Status:** COMPLETED
**Date:** 2025-11-23

# Summary

| Metric | Value |
|--------|-------|
| Total Findings | 5 |
| BUG | 2 (fixed) |
| DESIGN | 3 (documented) |
| Unclassified | 0 |
| Layers Passed | 5/5 |

# Layer Results

## Layer 1: Data Handling
**Status:** ✓ PASSED

No discrepancies detected.

## Layer 2: Signal Computation
**Status:** ✓ PASSED (2 DESIGN findings)

| Finding | Classification | Description |
|---------|---------------|-------------|
| FIND-001 | DESIGN | RSI smoothing method differs |
| FIND-002 | DESIGN | SMA calculation order differs |

[...]

# Findings Detail

## FIND-001: RSI Smoothing Method
**Classification:** DESIGN
**Layer:** signals
**Rationale:** rustybt uses Wilder's smoothing, Backtrader uses EMA...
[...]
```

**And** CLI command:
```bash
rustybt-validate report <session_id>
# Report saved to: validation-sessions/{session_id}/report.md

rustybt-validate report <session_id> --format json
# JSON format for programmatic use
```

**And** reports saved to session directory

**Prerequisites:** Story 4.8 (comparison), Story 5.4 (classifications)

**Technical Notes:**
- Use markdown tables for readability
- Include all finding details
- Support JSON format for CI integration
- Auto-generate on session completion

---

## Story 7.2: Implement Layer Report Generator

As a developer,
I want reports per validation layer across all strategies,
So that layer-specific validation can be reviewed.

**Acceptance Criteria:**

**Given** multiple validated strategies
**When** layer report is generated
**Then** cross-strategy layer summary is produced:

**Layer report structure:**
```markdown
# Layer 2: Signal Computation - Validation Report

# Overview

Signal computation validation across all validated strategies.

# Strategy Results

| Strategy | Status | Findings | Notes |
|----------|--------|----------|-------|
| SMA Crossover | ✓ PASS | 2 DESIGN | RSI, SMA order |
| Mean Reversion | ✓ PASS | 0 | - |
| Momentum | ✓ PASS | 1 DESIGN | RSI smoothing |
| Multi-Factor | ✓ PASS | 1 DESIGN | MACD calculation |

# Common DESIGN Differences

## RSI Calculation (3 strategies affected)
rustybt uses Wilder's smoothing method, Backtrader uses EMA smoothing.
**User Impact:** RSI values may differ by ~0.5%
**Workaround:** None needed, both methods are valid.

[...]
```

**And** CLI command:
```bash
rustybt-validate report --layer signals
# Report saved to: docs/validation/layer-2-signals-report.md
```

**Prerequisites:** Story 7.1 (session reports)

**Technical Notes:**
- Aggregate findings across strategies
- Identify common patterns (same DESIGN across strategies)
- Help users understand layer-specific behaviors

---

## Story 7.3: Implement Strategy Report Generator

As a developer,
I want reports per strategy across all layers,
So that strategy-specific validation can be reviewed.

**Acceptance Criteria:**

**Given** a fully validated strategy
**When** strategy report is generated
**Then** comprehensive strategy summary is produced:

**Strategy report structure:**
```markdown
# SMA Crossover Strategy - Validation Report

# Strategy Overview

Simple Moving Average Crossover strategy validated against Backtrader.

**Parameters:**
- Fast Period: 10
- Slow Period: 30

# Validation Results

| Layer | Status | Findings |
|-------|--------|----------|
| Data Handling | ✓ PASS | 0 |
| Signal Computation | ✓ PASS | 2 DESIGN |
| Order Lifecycle | ✓ PASS | 0 |
| Broker Transactions | ✓ PASS | 0 |
| Portfolio Returns | ✓ PASS | 0 |

**Overall Status:** ✓ VALIDATED

# Findings Summary

[... detailed findings ...]

# Recommendations

- RSI values may differ slightly from Backtrader (see DESIGN-001)
- Strategy behaves identically for practical trading purposes
```

**And** CLI command:
```bash
rustybt-validate report --strategy sma_crossover
# Report saved to: docs/validation/strategy-sma-crossover-report.md
```

**Prerequisites:** Story 7.1 (session reports)

**Technical Notes:**
- Focus on single strategy across all layers
- Include recommendations for users
- Reference detailed findings

---

## Story 7.4: Implement Overall Status Dashboard

As a developer,
I want an overall validation status dashboard,
So that I can see the complete validation picture at a glance.

**Acceptance Criteria:**

**Given** all validation sessions
**When** status command is invoked
**Then** dashboard is displayed:

**CLI output:**
```bash
rustybt-validate status
#
# ═══════════════════════════════════════════════════════════════
#                    rustybt Validation Status
# ═══════════════════════════════════════════════════════════════
#
# Strategies Validated: 4/4
# ┌──────────────────┬───────────┬───────────┬────────────┐
# │ Strategy         │ Status    │ Findings  │ Last Run   │
# ├──────────────────┼───────────┼───────────┼────────────┤
# │ SMA Crossover    │ ✓ VALID   │ 5 (0 BUG) │ 2025-11-23 │
# │ Mean Reversion   │ ✓ VALID   │ 3 (0 BUG) │ 2025-11-23 │
# │ Momentum         │ ✓ VALID   │ 4 (0 BUG) │ 2025-11-24 │
# │ Multi-Factor     │ ✓ VALID   │ 6 (0 BUG) │ 2025-11-24 │
# └──────────────────┴───────────┴───────────┴────────────┘
#
# Layer Coverage: 5/5 (100%)
# ┌────────────────────┬────────┬─────────────────────────────┐
# │ Layer              │ Status │ Notes                       │
# ├────────────────────┼────────┼─────────────────────────────┤
# │ 1. Data Handling   │ ✓ PASS │ All strategies              │
# │ 2. Signals         │ ✓ PASS │ 4 DESIGN differences noted  │
# │ 3. Orders          │ ✓ PASS │ All strategies              │
# │ 4. Broker          │ ✓ PASS │ All strategies              │
# │ 5. Portfolio       │ ✓ PASS │ All strategies              │
# └────────────────────┴────────┴─────────────────────────────┘
#
# Findings Summary:
#   Total: 18
#   BUG: 6 (all fixed ✓)
#   DESIGN: 12 (all documented ✓)
#   Regression Tests: 6
#
# Overall Confidence: HIGH ███████████░ 92%
#
# ═══════════════════════════════════════════════════════════════
```

**And** JSON output for CI:
```bash
rustybt-validate status --format json
# {"strategies_validated": 4, "layers_covered": 5, "bugs_open": 0, ...}
```

**And** exit code for CI:
- Exit 0 if all strategies validated, no open bugs
- Exit 1 if any strategy failed or bugs open

**Prerequisites:** Story 7.1-7.3 (all report types)

**Technical Notes:**
- Use box-drawing characters for ASCII tables
- Calculate confidence based on coverage and findings
- Exit codes enable CI integration
- Refresh data from all sessions

---

## Story 7.5: Implement DESIGN Differences Documentation

As a developer,
I want auto-generated documentation for all DESIGN differences,
So that users understand framework behavioral differences.

**Acceptance Criteria:**

**Given** DESIGN-classified findings
**When** documentation generation is invoked
**Then** user-facing documentation is generated:

**docs/validation/design-differences.md:**
```markdown
# rustybt vs Backtrader: Design Differences

This document describes intentional design differences between rustybt and Backtrader discovered during validation.

# Signal Computation

## RSI Calculation Method

**Finding:** FIND-001, FIND-007, FIND-012

**Difference:**
- rustybt uses Wilder's smoothing (exponential moving average with α = 1/period)
- Backtrader uses standard EMA smoothing

**Impact:**
RSI values may differ by ~0.5% between frameworks. This does not affect trading signal timing in most cases.

**Recommendation:**
No action needed. Both methods are industry-standard approaches to RSI calculation.

---

## MACD Calculation

**Finding:** FIND-015

**Difference:**
- rustybt calculates MACD signal line using 9-period EMA
- Backtrader uses 9-period SMA by default

[...]

# Order Execution

[...]

# Broker Transactions

[...]
```

**And** auto-update when new DESIGN findings added

**And** CLI command:
```bash
rustybt-validate docs generate
# Generated: docs/validation/design-differences.md
# Generated: docs/validation/bug-fixes.md
```

**Prerequisites:** Story 5.4 (DESIGN classification)

**Technical Notes:**
- Group findings by layer/category
- Write in user-friendly language
- Include practical impact and recommendations
- Auto-regenerate to stay current

---

## Story 7.6: Implement Validation Completion Tracking

As a developer,
I want validation completion percentage tracked,
So that I know how much validation work remains.

**Acceptance Criteria:**

**Given** defined validation scope
**When** completion tracking is queried
**Then** progress is calculated:

**Completion calculation:**
```python
def calculate_completion() -> ValidationProgress:
    """Calculate overall validation completion."""
    # Strategy completion
    total_strategies = 4  # Defined in PRD
    validated_strategies = count_validated_strategies()

    # Layer completion per strategy
    total_layers = 5 * total_strategies  # 20 total
    completed_layers = count_completed_layers()

    # Finding resolution
    total_findings = count_all_findings()
    resolved_findings = count_resolved_findings()

    return ValidationProgress(
        strategy_completion=validated_strategies / total_strategies,
        layer_completion=completed_layers / total_layers,
        finding_resolution=resolved_findings / total_findings if total_findings > 0 else 1.0,
        overall=calculate_weighted_average(...)
    )
```

**And** CLI command:
```bash
rustybt-validate progress
#
# Validation Progress
# ═══════════════════
#
# Strategies: ████████░░ 3/4 (75%)
#   ✓ SMA Crossover
#   ✓ Mean Reversion
#   ✓ Momentum
#   ○ Multi-Factor (in progress)
#
# Layers: █████████░ 18/20 (90%)
#   Multi-Factor missing: signals, portfolio
#
# Findings: ██████████ 15/15 (100%)
#   All findings classified and resolved
#
# Overall: ████████░░ 88%
#
# Next Steps:
#   1. Complete Multi-Factor validation (2 layers remaining)
#   2. Generate final validation report
```

**Prerequisites:** Story 7.4 (status dashboard)

**Technical Notes:**
- Weight completion by importance (strategies > layers > findings)
- Track partial layer completion
- Suggest next actions based on gaps

---

## Story 7.7: Implement Next Actions Recommender

As a developer,
I want recommended next actions for validation,
So that I know what to work on next.

**Acceptance Criteria:**

**Given** current validation state
**When** next actions are queried
**Then** prioritized recommendations are provided:

**Recommendation logic:**
```python
def recommend_next_actions() -> list[Recommendation]:
    """Recommend next validation actions based on current state."""
    actions = []

    # Priority 1: Open bugs
    open_bugs = get_open_bug_findings()
    if open_bugs:
        actions.append(Recommendation(
            priority=1,
            action="Fix open bugs",
            details=f"{len(open_bugs)} BUG findings require fixes",
            command="rustybt-validate investigate --bugs"
        ))

    # Priority 2: Unclassified findings
    unclassified = get_unclassified_findings()
    if unclassified:
        actions.append(Recommendation(
            priority=2,
            action="Classify findings",
            details=f"{len(unclassified)} findings need classification",
            command="rustybt-validate investigate --unclassified"
        ))

    # Priority 3: Incomplete strategies
    incomplete = get_incomplete_strategies()
    if incomplete:
        actions.append(Recommendation(
            priority=3,
            action="Complete strategy validation",
            details=f"{incomplete[0]} has incomplete layers",
            command=f"rustybt-validate run {incomplete[0].session_id}"
        ))

    # Priority 4: Missing documentation
    if needs_documentation_update():
        actions.append(Recommendation(
            priority=4,
            action="Update documentation",
            details="DESIGN differences need documentation refresh",
            command="rustybt-validate docs generate"
        ))

    return sorted(actions, key=lambda x: x.priority)
```

**And** CLI integration:
```bash
rustybt-validate next
#
# Recommended Next Actions
# ════════════════════════
#
# 1. [HIGH] Fix open bugs (2 BUG findings)
#    Command: rustybt-validate investigate --bugs
#
# 2. [MEDIUM] Classify findings (3 unclassified)
#    Command: rustybt-validate investigate --unclassified
#
# 3. [LOW] Update documentation
#    Command: rustybt-validate docs generate
```

**Prerequisites:** Story 7.6 (completion tracking)

**Technical Notes:**
- Prioritize by impact (bugs > unclassified > incomplete > docs)
- Provide copy-pasteable commands
- Update dynamically based on state

---
