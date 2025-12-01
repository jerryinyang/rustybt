# Epic Technical Specification: Real rustybt Engine Integration

Date: 2025-11-29
Author: .smirk
Epic ID: X
Status: Final

---

## Overview

Epic X addresses a critical flaw in the validation framework: the current rustybt execution path implements a simplified homebrew broker/backtest simulation instead of using rustybt's actual engine. This defeats the core purpose of validation - we're comparing a mock against Backtrader, not rustybt against Backtrader.

This epic replaces the homebrew implementation with proper integration to rustybt's real `TradingAlgorithm`, `DataBundle/DataPortal`, broker simulation, and indicator library. Additionally, data ingestion is standardized to ensure both frameworks consume identical synthetic data through their native data loading mechanisms.

**Business Context:** The validation framework exists to prove rustybt's correctness through systematic comparison against Backtrader. Without this epic, all validation results are meaningless - they only prove that a custom mock behaves similarly to Backtrader, not that rustybt itself is correct.

## Objectives and Scope

**In Scope:**
- Analyze rustybt's engine architecture (TradingAlgorithm, DataPortal, Broker, Indicators)
- Design shared data fixture infrastructure for deterministic cross-framework comparison
- Reimplement `RustyBTValidatedStrategy` to use real `TradingAlgorithm`
- Reimplement `execute_rustybt.py` to use rustybt's actual backtest runner
- Reimplement all 4 validation strategies (SMA Crossover, Mean Reversion, Momentum, Multi-Factor)
- Verify 5-layer comparison tests work with real rustybt execution
- Update architecture documentation to reflect corrected implementation

**Out of Scope:**
- Backtrader strategy changes (existing implementations are correct and working)
- Comparator logic changes (Layer 1-5 comparators remain unchanged)
- Session management changes (SessionManager unchanged)
- CLI changes (commands unchanged)
- New strategy additions (only reimplement existing 4)
- Performance optimization (functional correctness is the goal)

## System Architecture Alignment

**Architecture Components Affected:**

| Component | Current State | Target State |
|-----------|---------------|--------------|
| `RustyBTValidatedStrategy` | Homebrew simulation (SimulatedPosition, _cash, _execute_order) | Wraps/extends real `TradingAlgorithm` |
| `execute_rustybt.py` | Manual row iteration with mock broker | Uses rustybt's actual backtest runner |
| Data loading | Ad-hoc DataFrame passing | DataBundle/DataPortal infrastructure |
| Indicators | Manual deque-based calculations | rustybt's indicator library |
| Order execution | `_execute_order()` homebrew | rustybt's broker simulation |

**Architecture Constraints:**
- Must maintain JSONL log schema compatibility (Layer 1-5 events)
- Must preserve CLI interface (`--strategy`, `--data`, `--output`, `--params`)
- Must produce deterministic results (seeded random, controlled data)
- Must not modify rustybt core (logging via hooks/wrappers only)

## Detailed Design

### Services and Modules

| Module | Responsibility | Changes Required |
|--------|----------------|------------------|
| `rustybt/validation/base_strategy.py` | Validated strategy base classes | **Major rewrite**: Remove `SimulatedPosition`, `_cash`, `_positions`, `_execute_order`, `_update_portfolio_value`, `_calculate_sharpe_ratio`. Replace with hooks into real TradingAlgorithm lifecycle. Keep `ValidatedStrategyMixin` logging infrastructure. |
| `rustybt/validation/execute_rustybt.py` | CLI wrapper for strategy execution | **Major rewrite**: Replace manual row iteration with `run_algorithm()` from `rustybt.utils.run_algo`. Configure proper sim_params, data_portal, trading calendar. |
| `rustybt/validation/generate_fixture.py` | Test data generation | **Enhancement**: Ensure output format compatible with rustybt DataBundle. Add helper to register fixture as valid data bundle. |
| `tests/validation/strategies/rustybt/*.py` | rustybt strategy implementations | **Reimplement**: Use rustybt's actual indicator library (`rustybt.indicators`) and order API (`order()`, `order_target()`). Remove deque-based manual indicator calculations. |
| `tests/validation/conftest.py` | pytest fixtures | **Enhancement**: Add data loading helpers for both frameworks consuming shared Parquet fixture. |

**Modules Preserved (No Changes):**
- `rustybt/validation/session.py` - SessionManager works as-is
- `rustybt/validation/models.py` - Data models unchanged
- `rustybt/validation/log_parser.py` - Log parsing unchanged
- `rustybt/validation/comparators.py` - Layer comparators unchanged
- `rustybt/validation/cli.py` - CLI commands unchanged
- `rustybt/validation/reporting.py` - Report generation unchanged
- `tests/validation/strategies/bt_strategies/*.py` - Backtrader strategies correct

### Data Models and Contracts

**Data Fixture Schema (Parquet):**
```
columns:
  - timestamp: datetime64[ns, UTC]
  - asset: string (e.g., "AAPL", "TEST_ASSET_0")
  - open: float64
  - high: float64
  - low: float64
  - close: float64
  - volume: int64
```

**JSONL Log Schema (Unchanged - compatibility required):**
```json
{
  "timestamp": "ISO8601 string (simulation time)",
  "logged_at": "ISO8601 string (wall clock)",
  "layer": "data|signals|orders|broker|portfolio",
  "event": "event_name",
  "asset": "symbol or null",
  "data": { /* layer-specific payload */ }
}
```

**Layer 1 (Data) Events:**
- `initialize` - Strategy initialization
- `bar_received` - Bar data received

**Layer 2 (Signals) Events:**
- `signal_computed` - Indicator/signal calculated
  - `data.signal_name`: indicator name
  - `data.signal_value`: computed value

**Layer 3 (Orders) Events:**
- `order_created` - Order submitted
  - `data.order_type`: "market"|"limit"|"stop"
  - `data.quantity`: signed quantity
  - `data.limit_price`: optional

**Layer 4 (Broker) Events:**
- `transaction_executed` - Fill executed
  - `data.data_fill_price`: execution price
  - `data.data_fill_quantity`: filled quantity
- `commission_charged` - Commission applied
  - `data.data_commission`: commission amount
- `slippage_applied` - Slippage applied
  - `data.data_slippage`: slippage amount
- `cash_updated` - Cash balance updated
  - `data.data_cash_balance`: current cash

**Layer 5 (Portfolio) Events:**
- `portfolio_value_updated` - NAV updated
  - `data.data_portfolio_value`: portfolio value
- `daily_return_calculated` - Return computed
  - `data.data_daily_return`: daily return
- `drawdown_updated` - Drawdown computed
  - `data.data_drawdown`: current drawdown
- `final_metrics` - End-of-backtest metrics
  - `data.data_sharpe_ratio`: Sharpe ratio

### APIs and Interfaces

**execute_rustybt.py CLI Interface (Preserved):**
```bash
python -m rustybt.validation.execute_rustybt \
    --strategy module.path.ClassName \
    --data /path/to/data.parquet \
    --output /path/to/output.jsonl \
    [--params '{"key": "value"}']
```

**Target Internal API - Using rustybt's run_algorithm:**
```python
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

# Configure backtest
result = run_algorithm(
    initialize=strategy.initialize,
    handle_data=strategy.handle_data,
    bundle='validation-fixture',  # or custom data loading
    start=pd.Timestamp('2020-01-01'),
    end=pd.Timestamp('2021-12-31'),
    capital_base=100000,
)
```

**RustyBTValidatedStrategy Target Interface:**
```python
class RustyBTValidatedStrategy(ValidatedStrategyMixin):
    """Validated strategy using real rustybt TradingAlgorithm."""

    def initialize(self, context):
        """Called by TradingAlgorithm.initialize hook."""
        self._log_event("data", "initialize", {...})
        # Subclass implementation

    def handle_data(self, context, data):
        """Called by TradingAlgorithm.handle_data hook."""
        self._log_event("data", "bar_received", {...})
        # Subclass implementation - uses real rustybt APIs:
        # - data.history() for indicator data
        # - order(), order_target() for trades
        # - context.portfolio for position/cash info
```

**Logging Hook Points (from rustybt events):**
- `TradingAlgorithm.initialize` → Layer 1: initialize
- `TradingAlgorithm.handle_data` → Layer 1: bar_received
- Indicator computation → Layer 2: signal_computed
- `order()` / `order_target()` → Layer 3: order_created
- Transaction events → Layer 4: transaction_executed, commission_charged
- Portfolio updates → Layer 5: portfolio_value_updated

### Workflows and Sequencing

**Validation Execution Flow (Current vs Target):**

```
CURRENT (Homebrew):
1. load_data() → Polars DataFrame
2. strategy = StrategyClass(log_path)
3. strategy.initialize(None)
4. for row in data:
     strategy.handle_data(None, row)  # Manual iteration
5. strategy.finalize()

TARGET (Real rustybt):
1. Register fixture as DataBundle
2. run_algorithm(
     initialize=strategy.initialize,
     handle_data=strategy.handle_data,
     bundle='validation-fixture',
     ...
   )
3. rustybt engine manages:
   - DataPortal data access
   - TradingCalendar session handling
   - Order execution through broker
   - Portfolio/position tracking
4. Strategy logs events via ValidatedStrategyMixin
```

**Integration Sequence Diagram:**
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ execute_rustybt │     │   run_algorithm │     │ ValidatedStrat  │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │ call run_algorithm()  │                       │
         │──────────────────────>│                       │
         │                       │   initialize()        │
         │                       │──────────────────────>│
         │                       │                       │ log(initialize)
         │                       │                       │────────────────>
         │                       │                       │
         │                       │   handle_data(bar1)   │
         │                       │──────────────────────>│
         │                       │                       │ log(bar_received)
         │                       │                       │────────────────>
         │                       │                       │ compute indicators
         │                       │                       │ log(signal_computed)
         │                       │                       │────────────────>
         │                       │                       │ order_target()
         │                       │                       │─────────────┐
         │                       │                       │<────────────┘
         │                       │                       │ log(order_created)
         │                       │                       │────────────────>
         │                       │  (broker executes)    │
         │                       │                       │ log(transaction)
         │                       │                       │────────────────>
         │                       │                       │
         │                       │   ... repeat bars     │
         │                       │                       │
         │                       │   (backtest ends)     │
         │                       │──────────────────────>│
         │                       │                       │ log(final_metrics)
         │                       │                       │────────────────>
         │   result              │                       │
         │<──────────────────────│                       │
```

## Non-Functional Requirements

### Performance

| Metric | Target | Rationale |
|--------|--------|-----------|
| Single strategy execution | < 30 seconds | Validation runs should be fast for developer iteration |
| Full 4-strategy suite | < 5 minutes | Matches PRD NFR21 requirement |
| Log file I/O | Minimal overhead | JSONL writes should not bottleneck execution |

**Notes:**
- Performance is secondary to correctness for this epic
- Real rustybt execution may be slower than homebrew due to full engine overhead
- Acceptable trade-off: slower execution in exchange for accurate validation

### Security

**Not Applicable** - Per architecture document, the validation framework:
- Does NOT handle live trading credentials
- Does NOT handle production data
- Does NOT require authentication
- Runs locally on developer machines only

### Reliability/Availability

| Requirement | Implementation |
|-------------|----------------|
| Deterministic results | Seeded random generation, fixed timestamps, controlled data |
| Graceful failure | Proper error handling with exit code 1 on failure |
| Log file integrity | Flush after each write to prevent data loss on crash |
| Session recovery | Existing SessionManager handles session state (unchanged) |

**Critical:** Results must be reproducible. Same data + same parameters = same log output.

### Observability

| Signal | Layer | Purpose |
|--------|-------|---------|
| Strategy execution logs | stderr | Debug output during execution |
| JSONL validation logs | file | Structured events for comparison |
| Exit codes | process | 0=success, 1=failure |
| Error tracebacks | stderr | Debug information on failures |

**Existing observability (unchanged):**
- Session logs in `validation-sessions/{session_id}/validation.log`
- Layer-specific reports in `validation-sessions/{session_id}/analysis/`

## Dependencies and Integrations

### Internal Dependencies (rustybt modules)

| Module | Usage | Version |
|--------|-------|---------|
| `rustybt.algorithm.TradingAlgorithm` | Base class for strategy execution | Current |
| `rustybt.utils.run_algo.run_algorithm` | Backtest execution entry point | Current |
| `rustybt.data.data_portal.DataPortal` | Data access during backtest | Current |
| `rustybt.api` | Trading API (order, order_target, symbol) | Current |
| `rustybt.finance.trading` | Trading calendar, sim_params | Current |

### External Dependencies (from pyproject.toml)

| Package | Version | Purpose |
|---------|---------|---------|
| `polars` | >=1.0 | Data loading and processing |
| `pyarrow` | >=18.0 | Parquet file handling |
| `pandas` | >=1.3.0,<3.0 | DataFrame compatibility for rustybt API |
| `pyyaml` | >=6.0 | Session and config management |
| `click` | >=4.0.0 | CLI interface |
| `backtrader` | >=1.9.78 | Reference framework (unchanged) |
| `pytest` | >=7.2.0 | Test framework (unchanged) |
| `exchange-calendars` | >=4.2.4 | Trading calendar handling |

### Integration Points

**1. DataBundle Integration:**
- Validation fixture must be loadable as a rustybt DataBundle
- Options: Register custom bundle OR use direct DataPortal initialization
- Story X.2 will determine optimal approach

**2. TradingAlgorithm Integration:**
- ValidatedStrategy hooks into TradingAlgorithm lifecycle
- Options: Inheritance, composition, or function-based (like docs example)
- Story X.1 will analyze best integration pattern

**3. Broker Transaction Events:**
- Need to capture fill, commission, slippage events from rustybt broker
- May require event hooks or post-execution log extraction
- Story X.3 will design logging hook points

**4. Backtrader Integration (Unchanged):**
- `execute_backtrader.py` continues to work as-is
- PandasData feed loads same Parquet fixture
- No changes to Backtrader strategy implementations

## Acceptance Criteria (Authoritative)

### Epic-Level Success Criteria

1. **AC-E1:** Shared synthetic data fixture generated once, consumed by both frameworks
2. **AC-E2:** rustybt loads data via its native DataBundle/DataPortal infrastructure
3. **AC-E3:** Backtrader loads same data via its PandasData feed (existing, working)
4. **AC-E4:** `RustyBTValidatedStrategy` wraps/extends actual `TradingAlgorithm`
5. **AC-E5:** `execute_rustybt.py` uses rustybt's real backtest runner
6. **AC-E6:** All 4 strategies reimplemented using rustybt API
7. **AC-E7:** JSONL logs capture events from rustybt's actual execution
8. **AC-E8:** 5-layer comparison tests pass with real rustybt execution

### Story-Level Acceptance Criteria

**X.1: Analyze rustybt Engine Integration Points**
- AC-X1.1: Document TradingAlgorithm lifecycle methods and signatures
- AC-X1.2: Identify event hooks for logging injection
- AC-X1.3: Document DataPortal API for data access
- AC-X1.4: Document Broker API for order/position tracking
- AC-X1.5: Create integration design document specifying approach

**X.2: Design Shared Data Fixture Infrastructure**
- AC-X2.1: Produce canonical Parquet file with OHLCV + asset + timestamp
- AC-X2.2: Deterministic data generation (seeded random)
- AC-X2.3: rustybt receives identical bars as Backtrader
- AC-X2.4: First bar, last bar, bar count match exactly

**X.3: Reimplement ValidatedStrategy Base Class**
- AC-X3.1: Remove SimulatedPosition, _cash, _execute_order from base class
- AC-X3.2: Inherit from or wrap TradingAlgorithm
- AC-X3.3: Log Layer 1-5 events from actual rustybt execution
- AC-X3.4: Preserve JSONL schema compatibility

**X.4: Reimplement rustybt Execution Wrapper**
- AC-X4.1: Use rustybt's DataBundle/DataPortal for data loading
- AC-X4.2: Use rustybt's backtest runner (not manual row iteration)
- AC-X4.3: Preserve CLI interface (--strategy, --data, --output, --params)
- AC-X4.4: Exit code 0 on success, 1 on failure
- AC-X4.5: Deterministic results on repeated runs

**X.5: Reimplement SMA Crossover Strategy**
- AC-X5.1: Use rustybt's SMA indicator (not manual calculation)
- AC-X5.2: Use rustybt's order API (not _execute_order)
- AC-X5.3: Same number of trades as Backtrader
- AC-X5.4: SMA values match (Layer 2 comparison)

**X.6: Reimplement Remaining 3 Strategies**
- AC-X6.1: Mean Reversion uses rustybt indicators for z-score
- AC-X6.2: Momentum uses rustybt RSI indicator
- AC-X6.3: Multi-Factor uses rustybt EMA, RSI, MACD indicators
- AC-X6.4: All strategies produce Layer 1-5 log events

**X.7: Verify 5-Layer Comparison Compatibility**
- AC-X7.1: Layer 1 tests execute without errors
- AC-X7.2: Layer 2 indicator values compared correctly
- AC-X7.3: Layers 3-5 tests execute and compare correctly
- AC-X7.4: All findings classified as BUG or DESIGN
- AC-X7.5: Zero false positives

**X.8: Update Documentation**
- AC-X8.1: Architecture docs updated to reflect real integration
- AC-X8.2: Strategy guides show correct rustybt API usage
- AC-X8.3: Outdated examples removed

## Traceability Mapping

| AC | Spec Section | Component(s) | Test Idea |
|----|--------------|--------------|-----------|
| AC-E1 | Data Models and Contracts | `generate_fixture.py`, `conftest.py` | Unit test: fixture loaded by both frameworks |
| AC-E2 | Workflows and Sequencing | `execute_rustybt.py`, DataPortal | Integration test: rustybt loads via bundle |
| AC-E3 | N/A (existing) | `execute_backtrader.py` | Existing tests pass |
| AC-E4 | Services and Modules | `base_strategy.py` | Unit test: no homebrew simulation code |
| AC-E5 | APIs and Interfaces | `execute_rustybt.py` | Integration test: run_algorithm called |
| AC-E6 | Services and Modules | `strategies/rustybt/*.py` | Unit tests per strategy |
| AC-E7 | Data Models and Contracts | `base_strategy.py` | Log schema validation |
| AC-E8 | N/A | `test_layer_*.py` | Full test suite passes |
| AC-X1.1-5 | N/A | Design document | Manual review |
| AC-X2.1-4 | Data Models and Contracts | `generate_fixture.py` | Bar comparison tests |
| AC-X3.1-4 | Services and Modules | `base_strategy.py` | Code review + unit tests |
| AC-X4.1-5 | APIs and Interfaces | `execute_rustybt.py` | CLI integration tests |
| AC-X5.1-4 | N/A | `sma_crossover.py` | Layer 2 comparison |
| AC-X6.1-4 | N/A | Remaining strategies | Layer 2 comparison |
| AC-X7.1-5 | N/A | `test_layer_*.py` | Full test suite |
| AC-X8.1-3 | N/A | `docs/` | Documentation review |

## Risks, Assumptions, Open Questions

### Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | rustybt TradingAlgorithm API may not support required logging hooks | Medium | High | Story X.1 analyzes API first; fallback to wrapper/composition pattern |
| R2 | DataBundle registration may require complex setup | Medium | Medium | Story X.2 explores direct DataPortal initialization as alternative |
| R3 | Indicator implementations may differ (warmup period, precision) | High | Medium | Document as DESIGN differences; adjust tolerance configs |
| R4 | Broker event capture may require rustybt core modifications | Low | High | Use post-execution log extraction from results object if hooks unavailable |
| R5 | Real rustybt execution slower than homebrew | Medium | Low | Accept trade-off; performance is secondary to correctness |
| R6 | Trading calendar/session handling may cause bar count mismatches | Medium | Medium | Ensure both frameworks use same calendar configuration |

### Assumptions

| ID | Assumption | Validation |
|----|------------|------------|
| A1 | rustybt's TradingAlgorithm can be extended/wrapped without core modifications | Verified in Story X.1 |
| A2 | rustybt has SMA, RSI, EMA, MACD indicators available | Check `rustybt.indicators` in Story X.1 |
| A3 | rustybt's `run_algorithm()` provides sufficient configuration options | Verified in Story X.1/X.4 |
| A4 | Existing Backtrader implementations are correct (reference standard) | Per PRD, Backtrader is the trusted baseline |
| A5 | JSONL log schema is sufficient for all Layer 1-5 events | Validated in Epics 1-8 |
| A6 | Comparator logic remains valid for real rustybt execution | Tested in Story X.7 |

### Open Questions

| ID | Question | Owner | Resolution Timeline |
|----|----------|-------|---------------------|
| Q1 | What is the best integration pattern for ValidatedStrategy? (inheritance vs composition vs function-based) | Story X.1 | Before X.3 |
| Q2 | How to register custom Parquet data as a rustybt bundle? | Story X.2 | Before X.4 |
| Q3 | Does rustybt have all required indicators (SMA, RSI, EMA, MACD, std dev)? | Story X.1 | Before X.5 |
| Q4 | How to capture broker transaction events (fill, commission) from rustybt? | Story X.1 | Before X.3 |
| Q5 | Does rustybt support trailing stop orders natively? | Story X.1 | Before X.6 |

## Test Strategy Summary

### Test Levels

| Level | Scope | Tools | Stories |
|-------|-------|-------|---------|
| Unit | Individual components (ValidatedStrategy logging, fixture generation) | pytest | X.2, X.3 |
| Integration | CLI execution, data loading, strategy-engine integration | pytest, subprocess | X.4, X.5, X.6 |
| System | Full 5-layer validation suite | pytest, existing test_layer_*.py | X.7 |

### Test Coverage by Story

**Story X.1 (Analysis):** No automated tests - produces design document

**Story X.2 (Data Fixture):**
- Test: Fixture generates valid Parquet with expected schema
- Test: rustybt loads fixture via DataBundle
- Test: Backtrader loads fixture via PandasData
- Test: Bar counts match between frameworks

**Story X.3 (ValidatedStrategy):**
- Test: No homebrew simulation code present (code inspection)
- Test: Log events produced in correct schema
- Test: Layer 1-5 events logged during execution

**Story X.4 (Execution Wrapper):**
- Test: CLI accepts --strategy, --data, --output, --params
- Test: Execution completes with exit code 0
- Test: JSONL log file produced
- Test: Deterministic output on repeated runs

**Story X.5 (SMA Crossover):**
- Test: SMA indicator values match Backtrader (Layer 2)
- Test: Trade count matches Backtrader (Layer 3)
- Test: No manual deque calculations in code

**Story X.6 (Remaining Strategies):**
- Test: Each strategy produces Layer 1-5 events
- Test: Indicator values compared (Layer 2)
- Test: rustybt indicator APIs used (code review)

**Story X.7 (Verification):**
- Test: `pytest tests/validation/test_layer_*.py` passes
- Test: All discrepancies classified as BUG or DESIGN
- Test: No false positives reported

**Story X.8 (Documentation):**
- Manual review: Architecture docs updated
- Manual review: Strategy guides show correct API usage

### Edge Cases and Known Differences

| Case | Expected Behavior | Test Approach |
|------|-------------------|---------------|
| Warmup period | Different indicator values during warmup | Compare after warmup period; document as DESIGN |
| First/last bar | Potential timing differences | Allow timestamp tolerance; verify bar count |
| Order fill timing | Same-bar vs next-bar execution | Configure both frameworks identically |
| Commission calculation | $1 fixed per trade | Verify both use same commission model |
| Floating-point precision | Small differences expected | Use tolerance configs (1e-6 default) |

### Regression Test Plan

All tests added in this epic become permanent regression tests:
- Run on every PR via CI
- Part of validation test suite
- Prevent future regressions to homebrew implementation
