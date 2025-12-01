# Epic X: Real rustybt Engine Integration

## Overview

**Epic ID:** X
**Title:** Real rustybt Engine Integration
**Priority:** Critical (Blocker for validation framework validity)
**Status:** Approved
**Created:** 2025-11-29
**Approved:** 2025-11-29
**Total Points:** 26

## Problem Statement

The validation framework's rustybt execution path currently implements a simplified
homebrew broker/backtest simulation instead of using rustybt's actual engine. This
defeats the core purpose of validation - we're comparing a mock against Backtrader,
not rustybt against Backtrader.

Additionally, data ingestion must be standardized to ensure both frameworks consume
identical synthetic data through their native data loading mechanisms.

## Objective

Integrate the validation framework with rustybt's actual backtest engine so that:
1. Strategies execute using rustybt's real TradingAlgorithm
2. Orders flow through rustybt's real broker simulation
3. Indicators use rustybt's real indicator library
4. Data handling uses rustybt's real data infrastructure
5. Both frameworks load identical data through their native mechanisms

## Success Criteria

1. Shared synthetic data fixture generated once, consumed by both frameworks
2. rustybt loads data via its native DataBundle/DataPortal infrastructure
3. Backtrader loads same data via its PandasData feed (existing, working)
4. `RustyBTValidatedStrategy` wraps/extends actual `TradingAlgorithm`
5. `execute_rustybt.py` uses rustybt's real backtest runner
6. All 4 strategies reimplemented using rustybt API
7. JSONL logs capture events from rustybt's actual execution
8. 5-layer comparison tests pass with real rustybt execution

---

## Story X.1: Analyze rustybt Engine Integration Points

**Story ID:** X.1
**Title:** Analyze rustybt Engine Integration Points
**Points:** 3
**Priority:** Critical
**Status:** TODO

### Description

Before any implementation, thoroughly analyze rustybt's actual engine architecture
to identify:
- How TradingAlgorithm lifecycle works (initialize, handle_data, etc.)
- How to inject logging hooks without modifying core rustybt
- How DataBundle/DataPortal loads and serves data
- How orders are submitted and filled through the broker
- How indicators are computed and accessed

### Acceptance Criteria

```gherkin
Given the rustybt codebase
When I analyze the TradingAlgorithm class and related modules
Then I document:
  - TradingAlgorithm lifecycle methods and their signatures
  - Event hooks available for logging injection
  - DataPortal API for data access during backtest
  - Broker API for order submission and position tracking
  - Indicator computation patterns

Given the analysis is complete
When I create an integration design document
Then it specifies:
  - How ValidatedStrategy will inherit/wrap TradingAlgorithm
  - Where logging calls will be inserted
  - How data will flow from fixture to DataPortal
  - How orders and fills will be captured for Layer 3-4 logs
```

### Technical Notes

- Review `rustybt/algorithm/` for TradingAlgorithm implementation
- Review `rustybt/data/` for DataBundle and DataPortal
- Review `rustybt/broker/` for order execution
- Review `rustybt/indicators/` for indicator computation
- Output: Design document in `docs/internal/planning/epic-X-integration-design.md`

### Dependencies

- None (first story)

---

## Story X.2: Design Shared Data Fixture Infrastructure

**Story ID:** X.2
**Title:** Design Shared Data Fixture Infrastructure
**Points:** 2
**Priority:** Critical
**Status:** TODO

### Description

Design and implement data fixture infrastructure that ensures both rustybt and
Backtrader consume **identical** synthetic data through their **native** data
loading mechanisms.

### Acceptance Criteria

```gherkin
Given a synthetic data fixture generator
When I generate validation test data
Then it produces:
  - A canonical Parquet file with OHLCV + asset + timestamp
  - Deterministic data (seeded random generation)
  - Configurable date range, assets, and data characteristics

Given the shared Parquet fixture
When rustybt loads it via DataBundle/DataPortal
Then it receives identical OHLCV bars as Backtrader

Given the shared Parquet fixture
When Backtrader loads it via PandasData feed
Then it receives identical OHLCV bars as rustybt

Given both frameworks have loaded data
When I compare first bar, last bar, and bar count
Then they match exactly (timestamp, OHLC, volume)
```

### Technical Notes

- Enhance `generate_fixture.py` if needed for deterministic generation
- Create helper in `conftest.py` to load fixture for both frameworks
- May need adapter to convert Parquet → rustybt DataBundle format
- Verify timestamp handling (timezone-naive vs aware)
- Verify OHLCV column naming conventions match

### Dependencies

- Story X.1 (need to understand rustybt's data loading API)

---

## Story X.3: Reimplement ValidatedStrategy Base Class

**Story ID:** X.3
**Title:** Reimplement ValidatedStrategy Base Class
**Points:** 5
**Priority:** Critical
**Status:** TODO

### Description

Rewrite `RustyBTValidatedStrategy` to properly integrate with rustybt's actual
`TradingAlgorithm`. Remove all homebrew broker simulation and instead capture
events from rustybt's real execution.

### Acceptance Criteria

```gherkin
Given the current RustyBTValidatedStrategy
When I rewrite it to use real rustybt
Then it:
  - Inherits from or wraps TradingAlgorithm
  - Does NOT contain SimulatedPosition, _cash, _execute_order
  - Logs events by hooking into TradingAlgorithm lifecycle
  - Produces JSONL in same schema as current implementation

Given a strategy extends RustyBTValidatedStrategy
When the strategy runs through rustybt's engine
Then Layer 1-5 events are logged:
  - Layer 1 (data): bar_received from actual DataPortal
  - Layer 2 (signals): indicator values from rustybt indicators
  - Layer 3 (orders): order_created from rustybt order API
  - Layer 4 (broker): fills, commissions from rustybt broker
  - Layer 5 (portfolio): portfolio value from rustybt portfolio

Given the new ValidatedStrategy
When compared to Backtrader's ValidatedStrategy
Then log schemas are compatible for comparison
```

### Technical Notes

- Remove: `SimulatedPosition`, `_cash`, `_positions`, `_execute_order`,
  `_update_portfolio_value`, `_calculate_sharpe_ratio`
- Keep: `_log_event`, `log_signal`, `log_order_created`, JSONL file handling
- Integration approach depends on X.1 findings (inheritance vs composition)
- May need to use rustybt's event system if available
- Fallback: Wrap method calls to inject logging

### Dependencies

- Story X.1 (integration design)
- Story X.2 (data infrastructure)

---

## Story X.4: Reimplement rustybt Execution Wrapper

**Story ID:** X.4
**Title:** Reimplement rustybt Execution Wrapper
**Points:** 3
**Priority:** Critical
**Status:** TODO

### Description

Rewrite `execute_rustybt.py` to use rustybt's actual backtest runner instead of
manually iterating through data rows.

### Acceptance Criteria

```gherkin
Given the current execute_rustybt.py
When I rewrite it to use real rustybt
Then it:
  - Loads data via rustybt's DataBundle/DataPortal
  - Creates a proper backtest environment (sim_params, etc.)
  - Runs the strategy through rustybt's engine
  - Does NOT manually iterate through rows

Given I run: python -m rustybt.validation.execute_rustybt --strategy ... --data ... --output ...
When the strategy completes
Then:
  - JSONL log file is produced
  - Log contains events from rustybt's actual execution
  - Exit code 0 on success, 1 on failure

Given identical data and strategy parameters
When I run execute_rustybt multiple times
Then results are deterministic (same log output)
```

### Technical Notes

- Study rustybt's existing backtest runner/CLI if available
- Configure: start date, end date, starting capital, commission model
- Match Backtrader configuration: $100,000 starting cash, $1 per trade commission
- Ensure proper cleanup on success/failure
- Preserve CLI interface (--strategy, --data, --output, --params)

### Dependencies

- Story X.3 (ValidatedStrategy must be ready)
- Story X.2 (data loading infrastructure)

---

## Story X.5: Reimplement SMA Crossover Strategy

**Story ID:** X.5
**Title:** Reimplement SMA Crossover Strategy
**Points:** 3
**Priority:** High
**Status:** TODO

### Description

Reimplement the SMA Crossover strategy for rustybt using rustybt's actual
indicator library and order API. This serves as the reference pattern for
reimplementing the remaining strategies.

### Acceptance Criteria

```gherkin
Given the current sma_crossover.py for rustybt
When I reimplement it using rustybt API
Then it:
  - Uses rustybt's SMA indicator (not deque-based manual calculation)
  - Uses rustybt's order API (not _execute_order)
  - Extends the new RustyBTValidatedStrategy
  - Produces correct Layer 1-5 log events

Given identical parameters (fast=10, slow=30, target=100%)
When SMA Crossover runs on both rustybt and Backtrader
Then:
  - Same number of trades are executed
  - Trade timestamps align (within tolerance)
  - Signal values match (SMA calculations)

Given the reimplemented strategy
When I run the 5-layer comparison tests
Then Layer 2 (signals) shows matching SMA values
```

### Technical Notes

- Find rustybt's SMA indicator: likely in `rustybt/indicators/`
- Study how Backtrader's SMA works for parity
- May need warmup period handling to match Backtrader
- Document any intentional differences as DESIGN findings

### Dependencies

- Story X.4 (execution wrapper must be ready)

---

## Story X.6: Reimplement Remaining 3 Strategies

**Story ID:** X.6
**Title:** Reimplement Remaining 3 Strategies
**Points:** 5
**Priority:** High
**Status:** TODO

### Description

Reimplement the remaining 3 strategies (Mean Reversion, Momentum, Multi-Factor)
using rustybt's actual API, following the pattern established in Story X.5.

### Acceptance Criteria

```gherkin
Given the SMA Crossover pattern from Story X.5
When I reimplement Mean Reversion strategy
Then it:
  - Uses rustybt's indicators for z-score calculation
  - Uses rustybt's order API
  - Produces Layer 1-5 log events

Given the SMA Crossover pattern from Story X.5
When I reimplement Momentum strategy (RSI + trailing stops)
Then it:
  - Uses rustybt's RSI indicator
  - Uses rustybt's trailing stop order type (if available)
  - Produces Layer 1-5 log events

Given the SMA Crossover pattern from Story X.5
When I reimplement Multi-Factor strategy (EMA + RSI + MACD)
Then it:
  - Uses rustybt's EMA, RSI, MACD indicators
  - Combines signals correctly
  - Produces Layer 1-5 log events

Given all 4 strategies reimplemented
When I run each against its Backtrader counterpart
Then comparison tests can execute (pass/fail TBD in X.7)
```

### Technical Notes

- Mean Reversion: May need standard deviation indicator
- Momentum: Check if rustybt supports trailing stops natively
- Multi-Factor: Ensure indicator combination logic matches Backtrader
- Document any rustybt API gaps discovered

### Dependencies

- Story X.5 (pattern established)

---

## Story X.7: Verify 5-Layer Comparison Compatibility

**Story ID:** X.7
**Title:** Verify 5-Layer Comparison Compatibility
**Points:** 3
**Priority:** High
**Status:** TODO

### Description

Run the full 5-layer validation test suite with the reimplemented rustybt
strategies. Verify comparators work correctly with real rustybt logs.
Investigate and classify any discrepancies discovered.

### Acceptance Criteria

```gherkin
Given all 4 strategies reimplemented for rustybt
When I run the Layer 1 (data) comparison tests
Then:
  - Tests execute without errors
  - Bar counts match between frameworks
  - Timestamps align (within tolerance)
  - Any discrepancies are investigated

Given all 4 strategies reimplemented
When I run the Layer 2 (signals) comparison tests
Then:
  - Indicator values compared correctly
  - Signal timing compared correctly
  - Known DESIGN differences documented

Given all 4 strategies reimplemented
When I run the Layer 3-5 comparison tests
Then:
  - Order lifecycle events compared
  - Broker transactions compared
  - Portfolio metrics compared
  - All findings classified as BUG or DESIGN

Given the full test suite has run
When I review results
Then:
  - Zero false positives (correct behavior not flagged)
  - All real discrepancies detected
  - Findings documented in session
```

### Technical Notes

- Run: `pytest tests/validation/test_layer_*.py -v`
- May need to adjust tolerance configs for real rustybt
- Document any comparator bugs discovered
- Create regression tests for any BUG findings

### Dependencies

- Story X.6 (all strategies ready)

---

## Story X.8: Update Documentation

**Story ID:** X.8
**Title:** Update Documentation
**Points:** 2
**Priority:** Medium
**Status:** TODO

### Description

Update architecture documentation and strategy implementation guides to reflect
the corrected implementation that uses rustybt's real engine.

### Acceptance Criteria

```gherkin
Given the corrected implementation is complete
When I update architecture.md
Then it:
  - Removes references to homebrew simulation
  - Documents actual TradingAlgorithm integration
  - Updates data flow diagrams
  - Notes any ADR amendments

Given the corrected implementation is complete
When I update strategy implementation guides
Then they:
  - Show correct rustybt API usage
  - Reference actual indicator library
  - Show real order submission patterns
  - Remove outdated examples

Given documentation is updated
When a developer reads the guides
Then they can implement new validated strategies correctly
```

### Technical Notes

- Update `docs/internal/planning/architecture.md`
- Update any strategy guides in `docs/validation/`
- Consider adding ADR for "Why we integrated with real rustybt"
- Archive/remove outdated documentation

### Dependencies

- Story X.7 (implementation verified working)

---

## Epic Summary

| Story | Title | Points | Dependencies | Status |
|-------|-------|--------|--------------|--------|
| X.1 | Analyze rustybt Engine Integration Points | 3 | None | TODO |
| X.2 | Design Shared Data Fixture Infrastructure | 2 | X.1 | TODO |
| X.3 | Reimplement ValidatedStrategy Base Class | 5 | X.1, X.2 | TODO |
| X.4 | Reimplement rustybt Execution Wrapper | 3 | X.2, X.3 | TODO |
| X.5 | Reimplement SMA Crossover Strategy | 3 | X.4 | TODO |
| X.6 | Reimplement Remaining 3 Strategies | 5 | X.5 | TODO |
| X.7 | Verify 5-Layer Comparison Compatibility | 3 | X.6 | TODO |
| X.8 | Update Documentation | 2 | X.7 | TODO |
| **Total** | | **26** | | |

## Dependency Graph

```
X.1 (Analysis)
  ↓
X.2 (Data Infrastructure)
  ↓
X.3 (ValidatedStrategy)
  ↓
X.4 (Execution Wrapper)
  ↓
X.5 (SMA Crossover)
  ↓
X.6 (Remaining Strategies)
  ↓
X.7 (Verification)
  ↓
X.8 (Documentation)
```

Stories are sequential due to tight dependencies. Limited parallelization possible.

---

## Affected Files

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

## Preserved Files (No Changes)

- `rustybt/validation/session.py`
- `rustybt/validation/models.py`
- `rustybt/validation/log_parser.py`
- `rustybt/validation/comparators.py`
- `rustybt/validation/cli.py`
- `rustybt/validation/reporting.py`
- `rustybt/validation/execute_backtrader.py`
- `tests/validation/strategies/bt_strategies/*.py`

---

## Reference Documents

- **Sprint Change Proposal:** `docs/sprint-change-proposal-2025-11-29.md`
- **PRD:** `docs/internal/planning/prd.md`
- **Architecture:** `docs/internal/planning/architecture.md`

---

_Epic created by Correct Course Workflow_
_Approved: 2025-11-29_
_For: .smirk_
