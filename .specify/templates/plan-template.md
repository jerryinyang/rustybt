# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [single/web/mobile - determines source structure]
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**All 7 principles MUST be validated for this feature:**

### ✅ I. Decimal Financial Computing
- [ ] Will this feature involve financial calculations, prices, or quantities?
- [ ] If YES: Confirm all monetary values will use `Decimal` type (NEVER `float`)
- [ ] If YES: Confirm OHLCV data stored as `pl.Decimal(precision=18, scale=8)`
- [ ] If NO: Document why financial precision not required

### ✅ II. Zero-Mock Enforcement
- [ ] Confirm NO hardcoded return values in production code
- [ ] Confirm NO validation functions that always succeed
- [ ] Confirm NO mocks/stubs/fakes in production code (tests use real implementations)
- [ ] Confirm all calculations are real (no simulated values)
- [ ] Plan includes verification: `scripts/detect_mocks.py --strict` must pass

### ✅ III. Strategy Reusability Guarantee
- [ ] Will this feature affect strategy execution or API?
- [ ] If YES: Confirm changes work identically in backtest, paper, and live modes
- [ ] If YES: Confirm `TradingAlgorithm` API remains consistent across modes
- [ ] If YES: Confirm optional live hooks don't break backtest compatibility
- [ ] If NO: Document why strategy API unaffected

### ✅ IV. Type Safety Excellence
- [ ] Confirm Python 3.12+ will be used
- [ ] Confirm 100% type hint coverage for public APIs
- [ ] Confirm `mypy --strict` compliance required
- [ ] Confirm Google-style docstrings for all public APIs
- [ ] Confirm `black` (line length 100) and `ruff` linting
- [ ] Confirm complexity limits: functions ≤50 lines, cyclomatic complexity ≤10

### ✅ V. Test-Driven Development
- [ ] Confirm 90%+ test coverage target (95%+ for financial modules)
- [ ] Confirm tests use real implementations (NO mocks of production code)
- [ ] Confirm property-based tests for financial calculations (Hypothesis, 1000+ examples)
- [ ] Confirm test organization mirrors source structure
- [ ] Confirm performance benchmarks if applicable (fail if >10% degradation)

### ✅ VI. Modern Data Architecture
- [ ] Will this feature involve data processing or storage?
- [ ] If YES: Confirm Polars used as primary DataFrame library
- [ ] If YES: Confirm Parquet used for any OHLCV storage
- [ ] If YES: Confirm standard schema with Decimal columns
- [ ] If YES: Confirm data validation (OHLCV relationships, outliers, temporal consistency)
- [ ] If NO: Document why data architecture not involved

### ✅ VII. Sprint Debug Discipline
- [ ] Confirm pre-flight checklist will be completed before any fixes
- [ ] Confirm fix documentation will be maintained in `docs/internal/sprint-debug/fixes/`
- [ ] Confirm verification checklist will be run before commits
- [ ] If documentation changes: Confirm API signatures verified with `inspect.signature()`
- [ ] If documentation changes: Confirm code examples will be tested (not assumed)

**Constitution Compliance Summary:**
- Principles Applicable: [List which of the 7 apply to this feature]
- Principles Not Applicable: [List which don't apply and why]
- Violations Requiring Justification: [If any principle must be violated, document here with approval]

## Project Structure

### Documentation (this feature)

```
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
