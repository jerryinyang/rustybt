# Sprint Change Proposal: Real rustybt Engine Integration

**Document ID:** SCP-2025-11-29
**Date:** 2025-11-29
**Author:** Correct Course Workflow
**Status:** Pending Approval
**Requested By:** .smirk

---

## Section 1: Issue Summary

### Problem Statement

The validation framework's rustybt execution path implements a **simplified homebrew broker/backtest simulation** instead of using rustybt's actual engine. This fundamentally defeats the validation framework's core purpose of proving rustybt's correctness by comparison to Backtrader.

### Context

**Discovery:** Code review of `base_strategy.py`, `execute_rustybt.py`, and strategy implementations revealed that the "rustybt" side of validation does not actually use rustybt.

**When Discovered:** During implementation review, November 2025.

### Evidence

**1. `execute_rustybt.py` (lines 227-252):**
```python
# Current: Manual data iteration - NOT using rustybt engine
strategy = strategy_class(log_path=args.output, starting_cash=100000.0, ...)
strategy.initialize(context=None)
for row_idx in range(len(data)):
    row = data.row(row_idx, named=True)
    strategy.handle_data(context=None, data=row)
```

**2. `base_strategy.py` - `RustyBTValidatedStrategy`:**
- Contains standalone `SimulatedPosition` class
- Contains `_cash`, `_positions`, `_execute_order()` - homebrew broker
- Does NOT inherit from rustybt's `TradingAlgorithm`

**3. `sma_crossover.py` for rustybt:**
- Implements SMA via manual `deque`-based calculation
- Does NOT use rustybt's indicator library

**Consequence:** Even if all 5 validation layers pass with 100% agreement, it proves NOTHING about rustybt's correctness - it only proves our simplified simulation matches Backtrader.

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Impact Level | Description |
|------|-------------|-------------|
| Epic 1: Foundation | **High** | ValidatedStrategy base classes need complete redesign |
| Epic 2: Strategy Comparison | **High** | Execution must use real rustybt engine |
| Epic 3: Session Management | Low | Infrastructure is framework-agnostic, no changes |
| Epic 4: 5-Layer Test Suite | Medium | Comparators may need adjustment for real rustybt logs |
| Epic 5: Investigation Workflow | Low | Workflow is correct, only inputs change |
| Epic 6: Strategy Validation | **High** | All 4 strategies must use rustybt API |
| Epic 7: Reporting | Low | Reporting logic unchanged |
| Epic 8: Documentation | Medium | Guides need updating |

### Story Impact

Stories requiring rework are consolidated into **new Epic X** (see Section 4).

### Artifact Conflicts

| Artifact | Conflict | Resolution |
|----------|----------|------------|
| **PRD** | States "compare rustybt vs Backtrader" - current implementation doesn't | No PRD change needed; implementation must match PRD intent |
| **Architecture** | States "Zero Mock Enforcement" - violated by homebrew simulation | Minor update to document actual integration |
| **Architecture ADR-002** | Log-based validation correct, but rustybt side not using real framework | Add clarifying note |

### Technical Impact

| Component | Impact |
|-----------|--------|
| `rustybt/validation/base_strategy.py` | Major rewrite |
| `rustybt/validation/execute_rustybt.py` | Major rewrite |
| `rustybt/validation/generate_fixture.py` | Enhancement for dual-format data |
| `tests/validation/strategies/rustybt/*.py` | All 4 strategies reimplemented |
| `tests/validation/conftest.py` | Add data fixture helpers |

### Preserved Infrastructure (No Changes Required)

- Session management (`session.py`, `models.py`)
- Log parsing (`log_parser.py`)
- Comparators (`comparators.py`)
- CLI (`cli.py`)
- Reporting (`reporting.py`)
- Backtrader execution (`execute_backtrader.py`)
- All Backtrader strategies (`tests/validation/strategies/bt_strategies/`)

---

## Section 3: Recommended Approach

### Selected Path: Direct Adjustment

**Approach:** Fix specific modules while preserving working infrastructure. All corrections consolidated into a single new Epic X.

### Rationale

| Factor | Assessment |
|--------|------------|
| **Preserves work** | ~60% of completed infrastructure remains valid |
| **Contained risk** | Changes isolated to specific modules |
| **Scope unchanged** | MVP requirements remain the same |
| **No rollback needed** | Infrastructure is valuable, not broken |

### Alternatives Considered

| Option | Assessment | Decision |
|--------|------------|----------|
| **Rollback** | Nothing to rollback; infrastructure valuable | Rejected |
| **MVP Scope Reduction** | Scope is correct; only implementation wrong | Rejected |
| **Start Over** | Would discard working infrastructure | Rejected |

### Trade-offs

**Pros:**
- Faster than starting over
- Preserves working session management, logging, comparison infrastructure
- Same success criteria achievable

**Cons:**
- Requires understanding rustybt internals for integration
- May discover rustybt API limitations during integration
- Tight story dependencies limit parallelization

---

## Section 4: Detailed Change Proposals

### New Epic X: Real rustybt Engine Integration

**Priority:** Critical (Blocker)
**Total Points:** 26
**Stories:** 8

#### Story Summary

| ID | Title | Points | Dependencies |
|----|-------|--------|--------------|
| X.1 | Analyze rustybt Engine Integration Points | 3 | None |
| X.2 | Design Shared Data Fixture Infrastructure | 2 | X.1 |
| X.3 | Reimplement ValidatedStrategy Base Class | 5 | X.1, X.2 |
| X.4 | Reimplement rustybt Execution Wrapper | 3 | X.2, X.3 |
| X.5 | Reimplement SMA Crossover Strategy | 3 | X.4 |
| X.6 | Reimplement Remaining 3 Strategies | 5 | X.5 |
| X.7 | Verify 5-Layer Comparison Compatibility | 3 | X.6 |
| X.8 | Update Documentation | 2 | X.7 |

#### Story X.1: Analyze rustybt Engine Integration Points

**Objective:** Before implementation, analyze rustybt's actual engine to identify integration points.

**Deliverables:**
- Document TradingAlgorithm lifecycle methods
- Identify logging hook injection points
- Document DataPortal API for data access
- Document Broker API for order/position tracking
- Create integration design document

---

#### Story X.2: Design Shared Data Fixture Infrastructure

**Objective:** Ensure both frameworks consume identical synthetic data through native mechanisms.

**Deliverables:**
- Canonical Parquet fixture with deterministic generation
- rustybt data loading via DataBundle/DataPortal
- Backtrader data loading via PandasData (existing)
- Verification that both frameworks see identical bars

---

#### Story X.3: Reimplement ValidatedStrategy Base Class

**Objective:** Rewrite `RustyBTValidatedStrategy` to use real rustybt.

**Changes:**
```
REMOVE:
- SimulatedPosition class
- _cash, _positions attributes
- _execute_order() method
- _update_portfolio_value() method
- _calculate_sharpe_ratio() method

KEEP:
- _log_event() method
- log_signal(), log_order_created() helpers
- JSONL file management

ADD:
- Integration with TradingAlgorithm
- Event capture from rustybt's actual execution
```

---

#### Story X.4: Reimplement rustybt Execution Wrapper

**Objective:** Use rustybt's actual backtest runner.

**Changes:**
```
OLD (execute_rustybt.py):
  for row_idx in range(len(data)):
      row = data.row(row_idx, named=True)
      strategy.handle_data(context=None, data=row)

NEW:
  # Use rustybt's actual runner
  engine = rustybt.create_backtest(
      strategy=strategy_class,
      data=data_portal,
      start=start_date,
      end=end_date,
      capital=100000,
      commission=1.0
  )
  engine.run()
```

---

#### Story X.5: Reimplement SMA Crossover Strategy

**Objective:** Reference pattern for strategy reimplementation.

**Changes:**
```
OLD:
  self._prices: deque[float] = deque(maxlen=slow_period)
  def _calculate_sma(self, period):
      return sum(prices_list[-period:]) / period

NEW:
  self.fast_sma = rustybt.indicators.SMA(period=10)
  self.slow_sma = rustybt.indicators.SMA(period=30)
```

---

#### Story X.6: Reimplement Remaining 3 Strategies

**Objective:** Apply X.5 pattern to Mean Reversion, Momentum, Multi-Factor.

**Strategies:**
- Mean Reversion: Use rustybt's z-score/stddev indicators
- Momentum: Use rustybt's RSI indicator + trailing stop orders
- Multi-Factor: Use rustybt's EMA, RSI, MACD indicators

---

#### Story X.7: Verify 5-Layer Comparison Compatibility

**Objective:** Run full test suite, investigate discrepancies.

**Tests:**
- `pytest tests/validation/test_layer_1_data.py`
- `pytest tests/validation/test_layer_2_signals.py`
- `pytest tests/validation/test_layer_3_orders.py`
- `pytest tests/validation/test_layer_4_broker.py`
- `pytest tests/validation/test_layer_5_portfolio.py`

---

#### Story X.8: Update Documentation

**Objective:** Reflect corrected implementation in docs.

**Files:**
- `docs/internal/planning/architecture.md`
- Strategy implementation guides
- Add ADR documenting the correction

---

## Section 5: Implementation Handoff

### Change Scope Classification: **Major**

This requires fundamental architectural integration that needs:
- Developer understanding of rustybt internals
- Potential API discovery if rustybt lacks needed hooks
- Careful integration testing

### Handoff Plan

| Role | Responsibility |
|------|----------------|
| **Development Team** | Execute Epic X stories sequentially |
| **Solution Architect** | Review X.1 integration design; advise on rustybt API usage |
| **QA/Validation** | Verify 5-layer tests pass after X.7 |

### Implementation Sequence

```
Week 1: X.1 (Analysis) → X.2 (Data Infrastructure)
Week 2: X.3 (ValidatedStrategy) → X.4 (Execution Wrapper)
Week 3: X.5 (SMA Crossover) → X.6 (Remaining Strategies)
Week 4: X.7 (Verification) → X.8 (Documentation)
```

### Success Criteria

1. `RustyBTValidatedStrategy` uses actual `TradingAlgorithm`
2. `execute_rustybt.py` uses rustybt's real backtest runner
3. Both frameworks load identical data through native mechanisms
4. All 4 strategies use rustybt's indicator library
5. 5-layer comparison tests execute successfully
6. All discrepancies classified as BUG (fixed) or DESIGN (documented)

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| rustybt API lacks logging hooks | Design adapter/wrapper pattern in X.1 |
| rustybt indicators differ from Backtrader | Document as DESIGN differences |
| Data format incompatibility | X.2 creates robust adapter layer |
| Integration complexity | Sequential stories with clear dependencies |

---

## Appendix A: Files Affected

| File | Change Type | Story |
|------|-------------|-------|
| `rustybt/validation/base_strategy.py` | Major rewrite | X.3 |
| `rustybt/validation/execute_rustybt.py` | Major rewrite | X.4 |
| `rustybt/validation/generate_fixture.py` | Enhancement | X.2 |
| `tests/validation/strategies/rustybt/sma_crossover.py` | Reimplement | X.5 |
| `tests/validation/strategies/rustybt/mean_reversion.py` | Reimplement | X.6 |
| `tests/validation/strategies/rustybt/momentum.py` | Reimplement | X.6 |
| `tests/validation/strategies/rustybt/multi_factor.py` | Reimplement | X.6 |
| `tests/validation/conftest.py` | Add helpers | X.2 |
| `docs/internal/planning/architecture.md` | Minor update | X.8 |
| `docs/internal/planning/epics/epic-X-*.md` | New file | X.1 |

## Appendix B: Preserved Files (No Changes)

- `rustybt/validation/session.py`
- `rustybt/validation/models.py`
- `rustybt/validation/log_parser.py`
- `rustybt/validation/comparators.py`
- `rustybt/validation/cli.py`
- `rustybt/validation/reporting.py`
- `rustybt/validation/execute_backtrader.py`
- `tests/validation/strategies/bt_strategies/*.py`
- All session management tests
- All comparator tests

---

**Document Status:** Ready for Review

**Next Steps:**
1. User approval of this proposal
2. Create Epic X file in `docs/internal/planning/epics/`
3. Update sprint-status.yaml with Epic X stories
4. Begin Story X.1 implementation
