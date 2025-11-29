# rustybt - Product Requirements Document

**Author:** .smirk
**Date:** 2025-11-23
**Version:** 1.0

---

## Executive Summary

This PRD defines requirements for a **comprehensive validation framework** that proves rustybt's correctness and reliability through systematic comparison against Backtrader, a battle-tested reference implementation.

**The Core Problem:** Users need confidence that rustybt produces accurate backtest results that closely match real-world trading outcomes. Without rigorous validation, users cannot trust that a backtest showing +15% return would actually achieve that performance in live trading.

**The Solution:** Build a Test-Driven Development (TDD) validation system that:
1. Compares identical strategies implemented in both rustybt and Backtrader
2. Systematically validates all 5 critical layers (data handling, signal computation, order lifecycle, broker transactions, portfolio returns)
3. Detects and investigates every discrepancy to classify as either BUG (must fix) or DESIGN (intentional difference, must document)
4. Provides complete traceability and resumability for ongoing validation efforts

### What Makes This Special

**This is a detective project** - a systematic investigation framework that discovers discrepancies across every layer of the trading framework, investigates root causes through source code audits, and definitively classifies each finding.

Unlike typical testing that proves "it works," this validation framework proves **"it works correctly by comparison to a trusted reference."** Every discrepancy becomes a learning opportunity that either fixes a bug or documents an intentional design choice.

The validation system is built for **ongoing use** - organized to track progress, prevent redundant investigations, detect regressions, and allow new strategies to be added over time as confidence grows.

---

## Project Classification

**Technical Type:** Developer Tool (Testing/Validation Framework)
**Domain:** Fintech (Algorithmic Trading)
**Complexity:** High

**Classification Rationale:**

This is a **developer tool** that validates another developer tool (rustybt trading framework). It combines:
- Test framework development (pytest-based comparison suite)
- Financial domain expertise (trading strategy validation)
- Scientific methodology (controlled comparison experiments)
- Data engineering (log processing and analysis)

**Domain Complexity - Fintech (High):**

The fintech/algorithmic trading domain requires:
- **Financial Calculation Accuracy:** Decimal precision, commission calculations, slippage modeling, portfolio valuations must be exact
- **Temporal Correctness:** No lookahead bias, correct bar alignment, proper signal timing
- **Risk Management:** Position sizing, stop-loss, portfolio risk metrics
- **Regulatory Awareness:** While not trading live, validation framework must prove compliance-ready calculations
- **Market Microstructure:** Understanding order execution, fill modeling, broker transaction simulation

**Key Domain Concerns Addressed:**
1. **Calculation Precision:** Decimal arithmetic validation ensures audit-compliant financial calculations
2. **Temporal Integrity:** Data handling tests prevent lookahead bias that would invalidate backtest results
3. **Transaction Cost Modeling:** Commission and slippage validation ensures realistic performance estimates
4. **Order Execution Fidelity:** Order lifecycle tests prove correct simulation of market behavior

---

## Success Criteria

The validation framework is successful when:

### Primary Success Criteria

1. **All 5 Validation Layers Passing**
   - Data Handling Layer: 100% of tests passing (no lookahead bias, correct bar alignment)
   - Signal Computation Layer: 100% of tests passing (indicator calculations match, signal timing aligns)
   - Order Lifecycle Layer: 100% of tests passing (order creation, execution, state transitions correct)
   - Broker Transaction Layer: 100% of tests passing (commissions, slippage, position tracking accurate)
   - Portfolio Returns Layer: 100% of tests passing (return calculations, portfolio valuations match)

2. **Zero BUG-Classified Issues Remaining**
   - All discovered bugs have been fixed
   - Regression tests prevent bugs from reoccurring
   - Source code audits confirm fixes are correct

3. **Complete DESIGN Documentation**
   - All intentional differences between rustybt and Backtrader are documented
   - Each DESIGN classification explains WHY the difference exists
   - Documentation guides users on behavior differences

### Confidence Metrics

4. **Minimum 3-4 Strategies Validated**
   - Simple to moderately complex strategies tested
   - Multiple strategy types covered (crossover, mean reversion, momentum, multi-factor)
   - Each strategy produces consistent, explainable results

5. **Investigation Traceability**
   - Every discrepancy has been investigated
   - Investigation results recorded with timestamps
   - No "unexplained" differences remain

### Operational Success

6. **Resumable Validation Process**
   - New strategies can be added without starting over
   - Progress tracking allows work to pause and resume
   - Session management prevents redundant investigations

7. **User Confidence Achieved**
   - Framework users (individual traders, institutions, researchers, community) can trust rustybt results
   - Documentation provides evidence of validation rigor
   - Clear comparison reports demonstrate correctness

---

## Product Scope

### MVP - Minimum Viable Product

The MVP is **full-featured with no compromises** - all 5 validation layers, complete infrastructure, and 3-4 validated strategies.

**Core Components (All Required for MVP):**

1. **Comprehensive Test Suite (Built Once, Reused Forever)**
   - Test framework covering all 5 validation layers
   - Structured log ingestion and parsing
   - Automated comparison algorithms
   - Discrepancy detection and reporting
   - Pass/fail determination with detailed diagnostics

2. **Strategy Comparison Infrastructure**
   - Dual implementation framework (rustybt + Backtrader)
   - Strategy audit checklist and process
   - Execution environment (same data, same parameters)
   - Log generation standardization
   - Result collection and organization

3. **Validation Session Management**
   - Session creation and initialization
   - Progress tracking per session
   - Timestamped execution records
   - Findings database (discrepancies, classifications, resolutions)
   - Resumability support

4. **Investigation & Classification Workflow**
   - Discrepancy investigation process
   - Source code audit procedures
   - BUG vs DESIGN classification criteria
   - Fix verification protocols
   - Documentation generation

5. **Initial Strategy Validation (3-4 Strategies)**
   - **Strategy 1:** Simple Moving Average Crossover
   - **Strategy 2:** Mean Reversion (z-score based)
   - **Strategy 3:** Momentum Strategy (RSI + trailing stops)
   - **Strategy 4:** Multi-Factor Strategy (EMA + RSI + MACD)

6. **Validation Layers (All 5 Required)**
   - **Layer 1:** Data Handling (lookahead bias, bar alignment, data integrity)
   - **Layer 2:** Signal Computation (indicator calculations, signal timing, signal counts)
   - **Layer 3:** Order Lifecycle (creation, execution, fills, state transitions)
   - **Layer 4:** Broker Transactions (commissions, slippage, positions, cash)
   - **Layer 5:** Portfolio Returns (return calculations, portfolio value, performance metrics)

### Growth Features (Post-MVP)

**Expanded Strategy Coverage:**
- Portfolio strategies (multi-asset allocation)
- Options strategies (if rustybt adds options support)
- Futures strategies (rollover handling)
- International markets (forex, commodities)
- High-frequency strategies (minute/tick data)
- Edge case strategies (market gaps, halts, corporate actions)

---

## Domain-Specific Requirements

### Fintech Algorithmic Trading Validation Requirements

**Financial Calculation Accuracy:**
- All monetary calculations must use Decimal precision (no floating-point errors)
- Commission calculations must match broker specifications exactly
- Slippage modeling must be consistent and verifiable
- Portfolio valuation must be accurate to the cent
- Return calculations must follow industry-standard methodologies

**Temporal Integrity (Critical for Backtesting):**
- **No Lookahead Bias:** Test must prove strategies cannot access future data
- **Bar Alignment:** OHLCV bars must align correctly across timestamps
- **Signal Timing:** Signals must fire at the correct bar/timestamp
- **Order Execution Timing:** Orders must execute at correct simulation time
- **Data Windowing:** Historical data windows must be temporally correct

**Order Execution Fidelity:**
- Market orders: Immediate fill at current price (with slippage)
- Limit orders: Fill only when price crosses limit threshold
- Stop orders: Trigger correctly based on price movements
- Order lifecycle: Created → Submitted → Filled/Cancelled states tracked
- Fill modeling: Realistic fill assumptions (not all orders fill instantly)

**Broker Transaction Simulation:**
- Commission models: Tiered, percentage, fixed, or combined
- Position tracking: Long/short positions tracked accurately
- Cash ledger: All debits/credits recorded correctly
- Margin calculations: If applicable, margin requirements enforced
- Transaction costs: Total cost of trades calculated correctly

**Performance Metrics Accuracy:**
- Returns: Daily, cumulative, annualized returns calculated correctly
- Risk metrics: Sharpe ratio, max drawdown, volatility computed accurately
- Portfolio analytics: Portfolio value, exposure, leverage tracked
- Benchmark comparison: If comparing to benchmarks, calculations must match

**Validation Rigor:**
- Controlled experiments: Same data, same parameters, isolate framework differences
- Reproducibility: Test results must be deterministic and reproducible
- Traceability: Every discrepancy traceable to source code
- Classification discipline: Clear criteria for BUG vs DESIGN classification

This section shapes all functional and non-functional requirements below.


---

## Functional Requirements

### Test Suite Development (Built Once, Reused Forever)

**FR1:** System can define test specifications for all 5 validation layers (data handling, signal computation, order lifecycle, broker transactions, portfolio returns)

**FR2:** System can ingest structured logs from both rustybt and Backtrader strategy executions

**FR3:** System can parse logs into standardized data structures for comparison

**FR4:** System can compare data handling logs to detect lookahead bias violations

**FR5:** System can compare data handling logs to detect bar alignment discrepancies

**FR6:** System can compare signal computation logs to validate indicator calculation accuracy

**FR7:** System can compare signal computation logs to verify signal timing alignment

**FR8:** System can compare signal computation logs to verify signal count matching

**FR9:** System can compare order lifecycle logs to validate order creation timing

**FR10:** System can compare order lifecycle logs to validate order execution correctness

**FR11:** System can compare order lifecycle logs to validate order state transitions

**FR12:** System can compare broker transaction logs to validate commission calculations

**FR13:** System can compare broker transaction logs to validate slippage modeling

**FR14:** System can compare broker transaction logs to validate position tracking

**FR15:** System can compare broker transaction logs to validate cash ledger accuracy

**FR16:** System can compare portfolio return logs to validate return calculations

**FR17:** System can compare portfolio return logs to validate portfolio valuations

**FR18:** System can compare portfolio return logs to validate performance metrics

**FR19:** System can detect discrepancies between rustybt and Backtrader logs for each validation layer

**FR20:** System can generate detailed discrepancy reports showing exact differences

**FR21:** System can provide pass/fail determination for each validation layer

**FR22:** System can provide diagnostic information for failed tests (expected vs actual values)

### Strategy Comparison Infrastructure

**FR23:** System can maintain identical strategy implementations for rustybt and Backtrader

**FR24:** System can audit strategy implementations for logical equivalence before execution

**FR25:** System can execute strategies using identical market data for both frameworks

**FR26:** System can execute strategies using identical parameters for both frameworks

**FR27:** System can ensure both strategies generate logs in expected format

**FR28:** System can collect logs from both framework executions

**FR29:** System can organize logs by strategy, session, and timestamp

**FR30:** System can validate log completeness before running test suite

### Validation Session Management

**FR31:** System can create new validation sessions for testing strategies

**FR32:** System can assign unique identifiers to each validation session

**FR33:** System can timestamp all session activities

**FR34:** System can track session progress (setup, execution, analysis, investigation, resolution)

**FR35:** System can record all test results per session

**FR36:** System can store findings (discrepancies discovered) per session

**FR37:** System can maintain session state for resumability

**FR38:** System can list all past sessions with summary information

**FR39:** System can retrieve detailed information about any past session

**FR40:** System can prevent duplicate investigations across sessions

### Investigation & Classification Workflow

**FR41:** System can present discovered discrepancies for investigation

**FR42:** System can link discrepancies to relevant source code locations in rustybt

**FR43:** System can link discrepancies to relevant source code locations in Backtrader

**FR44:** System can track investigation notes for each discrepancy

**FR45:** System can classify discrepancies as BUG (framework error requiring fix)

**FR46:** System can classify discrepancies as DESIGN (intentional difference to document)

**FR47:** System can record rationale for each BUG classification

**FR48:** System can record rationale for each DESIGN classification

**FR49:** System can track bug fixes applied to rustybt

**FR50:** System can verify bug fixes through re-execution of test suite

**FR51:** System can generate regression tests for fixed bugs

**FR52:** System can generate documentation for DESIGN-classified differences

**FR53:** System can mark discrepancies as resolved (fixed or documented)

**FR54:** System can detect regression (previously fixed bugs reappearing)

### Strategy Validation (Initial 3-4 Strategies)

**FR55:** System can validate Simple Moving Average Crossover strategy across all 5 layers

**FR56:** System can validate Mean Reversion (z-score) strategy across all 5 layers

**FR57:** System can validate Momentum (RSI + trailing stops) strategy across all 5 layers

**FR58:** System can validate Multi-Factor (EMA + RSI + MACD) strategy across all 5 layers

**FR59:** System can add new strategies to validation suite without disrupting existing validations

### Reporting & Documentation

**FR60:** System can generate validation reports per session (summary of findings)

**FR61:** System can generate validation reports per layer (all strategies tested for that layer)

**FR62:** System can generate validation reports per strategy (all layers tested for that strategy)

**FR63:** System can generate overall validation status report (all sessions, all strategies, all layers)

**FR64:** System can export discrepancy classifications (BUG vs DESIGN) with rationale

**FR65:** System can generate user-facing documentation of DESIGN differences

**FR66:** System can track validation completion percentage

**FR67:** System can identify next recommended validation actions

### Data & Configuration Management

**FR68:** System can configure test tolerances for numerical comparisons (e.g., decimal precision)

**FR69:** System can configure test expectations per validation layer

**FR70:** System can manage reference data sets for strategy testing

**FR71:** System can version test suite specifications

**FR72:** System can version strategy implementations

**FR73:** System can track rustybt version tested against Backtrader version

---

## Non-Functional Requirements

### Accuracy & Correctness

**NFR1:** Numerical comparisons must account for floating-point vs Decimal precision differences (configurable tolerance thresholds)

**NFR2:** Test suite must have zero false positives (must not flag correct behavior as incorrect)

**NFR3:** Test suite must have zero false negatives (must catch all actual discrepancies)

**NFR4:** Log parsing must be robust to minor format variations without losing data

**NFR5:** Test results must be deterministic (same inputs always produce same results)

### Reliability & Robustness

**NFR6:** System must handle partial log files gracefully (detect incomplete logs)

**NFR7:** System must recover from test failures without corrupting session state

**NFR8:** System must maintain data integrity across session interruptions

**NFR9:** System must validate all inputs before processing (strategy logs, configurations)

**NFR10:** System must prevent data loss during investigation and classification workflows

### Maintainability & Extensibility

**NFR11:** Test suite code must be modular (each layer independently testable)

**NFR12:** Adding new validation layers must not require changing existing layers

**NFR13:** Adding new strategies must use same test suite without modifications

**NFR14:** Test specifications must be documented and version-controlled

**NFR15:** Code must follow rustybt coding standards (Python 3.12+, type hints, docstrings)

### Usability & Developer Experience

**NFR16:** Test reports must be clear and actionable (show what failed and why)

**NFR17:** Discrepancy reports must show both expected and actual values side-by-side

**NFR18:** Session management CLI must be intuitive (create, list, resume, inspect sessions)

**NFR19:** Investigation workflow must guide user through classification process

**NFR20:** Documentation generation must be automated (no manual markdown editing)

### Performance (Execution Speed)

**NFR21:** Test suite execution must complete within reasonable time (< 5 minutes for all tests on 3-4 strategies)

**NFR22:** Log parsing must handle large log files efficiently (> 100MB logs)

**NFR23:** Session queries must be fast (< 1 second to list all sessions, < 2 seconds to load session details)

### Reproducibility & Traceability

**NFR24:** All test executions must be reproducible (same data, same results)

**NFR25:** All discrepancies must be traceable to specific log entries and source code lines

**NFR26:** All classifications (BUG/DESIGN) must include timestamps and author

**NFR27:** All bug fixes must reference the original discrepancy that triggered them

**NFR28:** Regression tests must reference the original bug they prevent

### Integration & Compatibility

**NFR29:** System must integrate with rustybt development workflow (same repo, same Python environment)

**NFR30:** System must support both rustybt and Backtrader installed in same environment

**NFR31:** System must work on developer machines (macOS, Linux, Windows)

**NFR32:** System must use pytest as test framework (familiar to Python developers)

**NFR33:** System must generate reports compatible with CI/CD systems (if added later)

---

## Summary

This PRD defines a **comprehensive validation framework** for proving rustybt's correctness through systematic comparison against Backtrader.

**What We're Building:**
- Complete test suite covering 5 validation layers (73 functional requirements)
- Strategy comparison infrastructure with session management
- Investigation and classification workflow (BUG vs DESIGN)
- Validation of 3-4 initial strategies (SMA crossover, mean reversion, momentum, multi-factor)

**Why It Matters:**
Users need confidence that rustybt produces accurate backtest results matching real-world trading outcomes. This validation framework provides that confidence through rigorous, traceable comparison against a proven reference implementation.

**Success Means:**
- All 5 validation layers passing 100% of tests
- Zero unresolved bugs
- All intentional design differences documented
- Repeatable, resumable validation process for ongoing framework development

_This PRD captures the complete requirements for the rustybt validation framework - a detective project that systematically proves correctness through comparison, investigation, and classification._

_Created through collaborative discovery between .smirk and PM agent._
