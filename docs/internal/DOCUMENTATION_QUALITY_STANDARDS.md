# RustyBT Documentation Quality Standards

**Version**: 1.0
**Created**: 2025-10-15 (Epic 11, Story 11.1)
**Status**: Active - Mandatory for All Documentation
**Scope**: All RustyBT user-facing documentation

---

## Purpose

This document establishes production-grade quality standards for all RustyBT documentation. These standards are **mandatory** for all documentation work and are enforced through automated testing, checklists, and expert review.

---

## Core Principles

### 1. Zero Documentation Debt
**Never ship documentation with known issues.**
- All issues must be resolved before marking work complete
- "We'll fix it later" is not acceptable
- Quality gates cannot be bypassed

### 2. Production-Grade Quality
**Every example must work in production.**
- All code examples must be executable
- All examples must produce correct, expected results
- No placeholders, mocks, or "TODO" examples

### 3. Framework Expertise Required
**Documentation created by framework experts, not inference.**
- Documenters must have used the API/feature in production code
- Source code must be analyzed before documenting
- Syntax inference without validation is prohibited

### 4. Comprehensive Validation
**Multi-level validation before approval.**
- Automated API verification (imports)
- Automated example execution testing
- Manual usage pattern validation
- Framework expert review

### 5. User-Centric Documentation
**Documentation serves users, not developers.**
- Clear, concise explanations
- Realistic examples and scenarios
- Complete workflows, not fragments
- Common pitfalls highlighted

---

## API Reference Standards

### 2.1 API Existence ✅ AUTOMATED
**All APIs must exist in source code.**

**Requirement**:
- Every documented class, function, method MUST exist in rustybt/ source code
- Must be production code (not test code, not mock code)
- Must be in the documented location

**Verification**:
- Automated: `scripts/verify_documented_apis.py`
- Pass Criteria: 100% verification rate
- Failure: Documentation rejected

**Examples**:
- ✅ `from rustybt.finance.execution import LimitOrder` (exists in source)
- ❌ `from rustybt.finance.execution import TWAPOrder` (does not exist)

---

### 2.2 Correct Import Paths ✅ AUTOMATED
**Import statements must be accurate.**

**Requirement**:
- Import paths must exactly match source code organization
- Module names must be correct
- No "it should be here" assumptions

**Verification**:
- Automated: `scripts/verify_documented_apis.py`
- Pass Criteria: All imports executable
- Failure: Documentation rejected

**Examples**:
- ✅ `from rustybt.algorithm import TradingAlgorithm`
- ❌ `from rustybt import TradingAlgorithm` (wrong path)

---

### 2.3 Usage Patterns ⚠️ EXPERT REVIEW
**API usage must reflect production patterns.**

**Requirement**:
- API usage examples must demonstrate actual production patterns
- Parameter combinations must be realistic and tested
- Workflows must be complete and functional
- Error handling must be shown where appropriate

**Verification**:
- Manual: Framework expert review
- Pass Criteria: Expert approval
- Failure: Documentation requires revision

**Examples**:
- ✅ Complete workflow showing realistic parameter usage
- ❌ Minimal example with unrealistic or untested parameters

---

### 2.4 Parameter Accuracy ⚠️ MANUAL
**All parameters, types, defaults must match source.**

**Requirement**:
- Parameter names must match source code exactly
- Parameter types must be accurate (with type hints where applicable)
- Default values must be correct
- Required vs optional parameters must be clear

**Verification**:
- Manual: Source code comparison
- Automated: Where possible via introspection
- Pass Criteria: 100% accuracy
- Failure: Documentation requires correction

**Examples**:
- ✅ `LimitOrder(asset, amount, limit_price, style=None)`
- ❌ `LimitOrder(symbol, qty, price)` (wrong parameter names)

---

### 2.5 Return Values ⚠️ MANUAL
**Return types and values must be accurate.**

**Requirement**:
- Return types must be documented correctly
- Return value descriptions must match actual behavior
- Edge cases and error conditions must be documented

**Verification**:
- Manual: Source code analysis + expert review
- Pass Criteria: Accurate return documentation
- Failure: Documentation requires correction

---

## Code Example Standards

### 3.1 Executable ✅ AUTOMATED
**100% of code examples must be executable.**

**Requirement**:
- Every code block marked as Python must execute without errors
- Examples must include all necessary imports
- Examples must include all necessary setup
- No "..." or "# code here" placeholders

**Verification**:
- Automated: `scripts/run_documented_examples.py`
- Pass Criteria: 100% execution success rate
- Failure: Documentation rejected

**Example**:
```python
# ✅ GOOD: Complete, executable example
from rustybt.algorithm import TradingAlgorithm
from rustybt.api import order, symbol

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        self.asset = symbol('AAPL')

    def handle_data(self, context, data):
        order(self.asset, 10)

# ❌ BAD: Incomplete example
class MyStrategy(TradingAlgorithm):
    ...  # Implementation here
```

---

### 3.2 Tested ✅ AUTOMATED + ⚠️ MANUAL
**All examples tested with automated harness.**

**Requirement**:
- Examples must be tested for execution
- Examples must be tested for correct output
- Complex examples must be manually verified for correctness

**Verification**:
- Automated: Example execution harness
- Manual: Expert review of example outputs
- Pass Criteria: Executes correctly with expected output
- Failure: Example must be corrected

---

### 3.3 Self-Contained ⚠️ MANUAL
**Examples include all necessary imports and setup.**

**Requirement**:
- All imports explicitly shown
- Required setup/configuration included or clearly documented
- No assumption of prior context
- Can be copy-pasted and run (with documented prerequisites)

**Verification**:
- Manual: Review for completeness
- Automated: Import verification
- Pass Criteria: Example is self-contained
- Failure: Add missing imports/setup

---

### 3.4 Realistic ⚠️ EXPERT REVIEW
**Examples use realistic data and scenarios.**

**Requirement**:
- Data must be realistic (e.g., actual symbol names, reasonable prices)
- Parameters must be realistic (e.g., actual date ranges, reasonable quantities)
- Workflows must reflect actual use cases
- No "foo", "bar", "test123" placeholder values

**Verification**:
- Manual: Expert review
- Pass Criteria: Examples demonstrate realistic usage
- Failure: Revise for realism

**Examples**:
- ✅ `symbol('AAPL')`, `order(asset, 100)`, date range 2020-2023
- ❌ `symbol('XXX')`, `order(asset, 999999)`, date range 1900-2000

---

### 3.5 Commented ⚠️ MANUAL
**Complex examples include explanatory comments.**

**Requirement**:
- Non-obvious logic must be explained
- Complex workflows must have step-by-step comments
- Simple examples don't require excessive commenting
- Comments explain "why", not just "what"

**Verification**:
- Manual: Readability review
- Pass Criteria: Complex examples are understandable
- Failure: Add clarifying comments

---

### 3.6 Best Practices ⚠️ EXPERT REVIEW
**Examples demonstrate best practices, not shortcuts.**

**Requirement**:
- Examples show production-quality patterns
- Error handling is demonstrated where appropriate
- Performance considerations are shown
- Anti-patterns are avoided
- If showing bad practice for learning, clearly marked as such

**Verification**:
- Manual: Expert review
- Pass Criteria: Examples demonstrate best practices
- Failure: Revise to show correct patterns

---

## Workflow Documentation Standards

### 4.1 Complete Workflows ⚠️ MANUAL
**Multi-step workflows show entire process.**

**Requirement**:
- All steps documented from start to finish
- No steps omitted or assumed
- Prerequisites clearly stated
- Expected outcomes clearly stated

**Example**:
- ✅ Complete data ingestion workflow (ingest → validate → store → use)
- ❌ Partial workflow (just ingest step, rest assumed)

---

### 4.2 Error Handling ⚠️ MANUAL
**Include error handling patterns.**

**Requirement**:
- Common errors documented
- Error handling demonstrated in examples
- Recovery strategies shown where applicable

**Example**:
```python
# ✅ GOOD: Shows error handling
try:
    data = ingest_data(source)
except DataSourceError as e:
    logger.error(f"Data ingestion failed: {e}")
    # Handle error appropriately

# ❌ BAD: No error handling shown
data = ingest_data(source)
```

---

### 4.3 Performance Notes ⚠️ EXPERT REVIEW
**Document performance implications where relevant.**

**Requirement**:
- Performance-critical operations must note implications
- Optimization strategies documented where applicable
- Trade-offs explained (e.g., memory vs speed)

---

### 4.4 Common Pitfalls ⚠️ EXPERT REVIEW
**Highlight common mistakes and how to avoid them.**

**Requirement**:
- Known pitfalls documented
- Incorrect usage examples shown (clearly marked)
- Correct alternatives provided

**Example**:
```python
# ❌ INCORRECT: Don't do this
# Creates new order object each time, losing state
def handle_data(context, data):
    order = LimitOrder(...)

# ✅ CORRECT: Reuse order object
def initialize(context):
    self.order = LimitOrder(...)

def handle_data(context, data):
    # Use self.order
```

---

## Validation Requirements

### 5.1 Pre-Flight Checklist ✅ MANDATORY
**Complete before starting documentation work.**

**Requirement**:
- `DOCUMENTATION_CREATION_CHECKLIST.md` must be completed
- All checklist items must be verified
- Checklist must be submitted with documentation

**Verification**:
- Manual: Checklist file submission
- Pass Criteria: All items checked
- Failure: Work cannot begin

---

### 5.2 During Creation ⚠️ CONTINUOUS
**Continuous validation during writing.**

**Requirement**:
- Test examples immediately after writing
- Run `verify_documented_apis.py` frequently
- Fix issues immediately (don't accumulate)

**Verification**:
- Self-directed during development
- Evidence in git history (frequent commits with fixes)

---

### 5.3 Pre-Submission ✅ MANDATORY
**Comprehensive checklist before QA.**

**Requirement**:
- `DOCUMENTATION_VALIDATION_CHECKLIST.md` must be 100% complete
- All automated tests must pass (100%)
- All checklist items must be verified with evidence
- Checklist must be submitted with documentation

**Verification**:
- Manual: QA review of checklist
- Automated: Test results
- Pass Criteria: 100% checklist completion + 100% test pass
- Failure: Documentation returned for correction

---

### 5.4 QA Validation ✅ MANDATORY
**Independent review by QA agent.**

**Requirement**:
- QA agent reviews validation checklist
- QA agent spot-checks documentation
- QA agent verifies automated test results
- QA agent provides pass/fail decision

**Verification**:
- Manual: QA agent review
- Pass Criteria: QA approval
- Failure: Returned to author for corrections

---

### 5.5 Expert Review ✅ MANDATORY
**Final review by framework maintainer/expert.**

**Requirement**:
- Framework expert reviews all documentation
- Expert validates usage patterns
- Expert validates technical accuracy
- Expert provides written approval

**Verification**:
- Manual: Expert review and sign-off
- Pass Criteria: Expert written approval
- Failure: Returned to author for corrections

**NO DOCUMENTATION IS COMPLETE WITHOUT EXPERT APPROVAL**

---

## Enforcement

### 6.1 Automated Testing ✅ AUTOMATED
**CI/CD pipeline runs verification scripts.**

**Enforcement**:
- `scripts/verify_documented_apis.py` runs on every commit (optional)
- `scripts/run_documented_examples.py` runs before story completion
- Failed tests block story completion
- No bypassing automated tests

---

### 6.2 Mandatory Checklists ✅ MANDATORY
**No documentation approved without completed checklists.**

**Enforcement**:
- Pre-flight checklist required to start work
- Validation checklist required to submit work
- QA verifies checklist completion
- Incomplete checklists = automatic rejection

---

### 6.3 Review Requirements ✅ MANDATORY
**Expert review is mandatory, not optional.**

**Enforcement**:
- No story marked complete without expert sign-off
- Expert review cannot be skipped "for efficiency"
- Expert feedback must be addressed
- Final approval must be written and archived

---

### 6.4 Quality Gates ✅ MANDATORY
**Documentation cannot be marked "Complete" until all gates pass.**

**Quality Gates**:
1. Pre-flight checklist complete ✅
2. Automated API verification: 100% pass ✅
3. Automated example execution: 100% pass ✅
4. Validation checklist: 100% complete ✅
5. QA approval ✅
6. Expert approval ✅

**Enforcement**:
- ALL gates must pass
- No partial approval
- No "good enough" exceptions
- Zero known issues at completion

---

## Consequences of Violations

### For Documentation Authors
- **Incomplete Checklists**: Work returned, must complete
- **Failed Automated Tests**: Work blocked until fixed
- **Bypassing Quality Framework**: Work rejected, must redo
- **Repeated Quality Issues**: May require additional training or removal from documentation work

### For Reviewers (QA/Expert)
- **Approving Non-Compliant Work**: Approval revoked, must re-review
- **Skipping Review Steps**: Review invalid, must complete properly
- **Pressure to Bypass Standards**: Report to project lead immediately

### For Project
- **Shipping Non-Compliant Documentation**: Documentation pulled from release
- **Discovered Quality Issues**: Story reopened, marked incomplete
- **User Trust Violation**: Immediate remediation required

---

## Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-10-15 | 1.0 | Initial creation for Epic 11 | John (PM Agent) |

---

## Related Documents

- **Creation Checklist**: `DOCUMENTATION_CREATION_CHECKLIST.md`
- **Validation Checklist**: `DOCUMENTATION_VALIDATION_CHECKLIST.md`
- **Epic 11**: `prd/epic-11-documentation-quality-framework-and-epic10-redo.md`
- **Sprint Change Proposal**: `qa/SPRINT_CHANGE_PROPOSAL_EPIC10_COMPLETE_REDO.md`

---

**Status**: ✅ ACTIVE - Mandatory for All Documentation Work
**Effective**: Immediately (Epic 11 Story 11.1 onwards)
**Review Cycle**: Quarterly or as needed

---

*These standards exist to ensure RustyBT documentation is trustworthy, accurate, and production-grade. User trust depends on documentation quality. No exceptions.*
