# Story 10.1.1: Create Audit Infrastructure & Findings Schema

Status: done

## Story

As a **developer**,
I want **a structured audit infrastructure with YAML-based findings storage**,
So that **audit findings are machine-readable, trackable, and version-controlled**.

## Acceptance Criteria

1. **AC1:** The audit infrastructure directory structure is created:
   - `tests/live/audit/` directory with `__init__.py`, `conftest.py`
   - `tests/live/audit/findings/` directory for YAML findings files
   - Sample findings file demonstrating the schema

2. **AC2:** The findings schema includes all required fields:
   - `id`: Finding ID using format `AUDIT-{MODULE_CODE}{NUMBER}` (E=Engine, B=Brokers, S=Streaming, O=OrderManager, R=Reconciler, C=CircuitBreakers)
   - `module`: Path to the affected module file
   - `line`: Line number where issue is located
   - `severity`: Classification (Critical/High/Medium/Low)
   - `category`: Type of issue (error_handling, concurrency, state_management, security, etc.)
   - `description`: Clear description of the issue
   - `recommendation`: Suggested fix
   - `status`: Lifecycle state (Open/In Progress/Resolved/Verified)
   - `found_by`: Method of discovery (code_audit, static_analysis, manual_review)
   - `found_at`: Date finding was created
   - `resolved_at`: Date finding was resolved (null if unresolved)
   - `regression_test`: Path to regression test (null if none)

3. **AC3:** Pytest fixtures for loading and validating findings are available in `conftest.py`:
   - Fixture to load all findings from YAML files
   - Fixture to filter findings by severity, module, or status
   - Fixture to validate findings schema
   - Fixture to get counts by severity

4. **AC4:** A sample findings file (`tests/live/audit/findings/sample_findings.yaml`) demonstrates the schema with at least 2 example findings of different severities

5. **AC5:** The findings YAML schema is validated via Pydantic or similar validation when loaded

## Tasks / Subtasks

- [x] Task 1: Create audit directory structure (AC: #1)
  - [x] Create `tests/live/audit/` directory
  - [x] Create `tests/live/audit/__init__.py`
  - [x] Create `tests/live/audit/findings/` directory
  - [x] Create `tests/live/audit/findings/__init__.py`

- [x] Task 2: Define findings schema as Pydantic model (AC: #2, #5)
  - [x] Create `tests/live/audit/models.py` with `AuditFinding` Pydantic model
  - [x] Define all required fields with proper types and validation
  - [x] Add severity enum (CRITICAL, HIGH, MEDIUM, LOW)
  - [x] Add status enum (OPEN, IN_PROGRESS, RESOLVED, VERIFIED)
  - [x] Add module code mapping for ID generation

- [x] Task 3: Create pytest fixtures in conftest.py (AC: #3)
  - [x] Create `load_all_findings()` fixture
  - [x] Create `findings_by_severity(severity)` fixture
  - [x] Create `findings_by_module(module_path)` fixture
  - [x] Create `findings_by_status(status)` fixture
  - [x] Create `validate_findings_schema(findings_path)` fixture
  - [x] Create `severity_counts()` fixture

- [x] Task 4: Create sample findings file (AC: #4)
  - [x] Create `tests/live/audit/findings/sample_findings.yaml`
  - [x] Add example CRITICAL finding for error handling
  - [x] Add example HIGH finding for state management
  - [x] Add example MEDIUM finding for logging
  - [x] Ensure all fields are populated correctly

- [x] Task 5: Write unit tests for audit infrastructure (AC: #1-5)
  - [x] Test directory structure exists
  - [x] Test schema validation accepts valid findings
  - [x] Test schema validation rejects invalid findings
  - [x] Test fixtures load and filter correctly
  - [x] Test severity counts are accurate

## Dev Notes

### Architecture Patterns and Constraints

This story establishes the foundation for the code audit process defined in Epic 10.1. The infrastructure follows Pattern 5 (Audit Finding Classification) from the Architecture document:

- Finding IDs use format: `AUDIT-{MODULE_CODE}{NUMBER}` where module codes are:
  - E = Engine (`rustybt/live/engine.py`)
  - B = Brokers (`rustybt/live/brokers/`)
  - S = Streaming (`rustybt/live/streaming/`)
  - O = OrderManager (`rustybt/live/order_manager.py`)
  - R = Reconciler (`rustybt/live/reconciler.py`)
  - C = CircuitBreakers (`rustybt/live/circuit_breakers.py`)

- Severity classification criteria:
  - **CRITICAL**: Data loss, financial impact, security vulnerabilities
  - **HIGH**: Incorrect behavior, state corruption, crash potential
  - **MEDIUM**: Edge case bugs, non-critical error handling
  - **LOW**: Code style, minor improvements, documentation

- Status lifecycle: OPEN → IN_PROGRESS → RESOLVED → VERIFIED
  - CRITICAL/HIGH findings MUST have regression tests before RESOLVED
  - VERIFIED status requires passing regression test

### Technology Stack

- **PyYAML >=6.0**: For YAML parsing (already in rustybt dependencies)
- **Pydantic**: For schema validation (if not already available, use dataclasses with manual validation)
- **pytest >=7.2.0**: Test framework (existing)

### Project Structure Notes

The audit infrastructure is placed in `tests/live/audit/` to align with the test organization patterns established in rustybt:
- Tests organized by domain (`tests/live/` for live trading tests)
- Fixtures in `conftest.py` following pytest conventions
- YAML data files in subdirectories (`findings/`)

This location was chosen per Architecture document FR Category mapping which specifies "Code Audit & Issue Management (FR1-FR5)" maps to `tests/live/audit/`.

### References

- [Source: docs/internal/planning/architecture-epic-10.md#Pattern 5: Audit Finding Classification]
- [Source: docs/internal/planning/architecture-epic-10.md#Project Structure]
- [Source: docs/internal/planning/prd-epic-10.md#Code Audit Requirements]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#Data Models and Contracts - Audit Finding Schema]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.1.1]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

claude-opus-4-5-20251101

### Debug Log References

Plan: Create audit directory structure, Pydantic models for schema validation, pytest fixtures, sample findings file, and comprehensive unit tests.

### Completion Notes List

- Created complete audit infrastructure with Pydantic-validated YAML schema
- Implemented all required fixtures for loading, filtering, and validating findings
- Sample findings file includes 4 examples (CRITICAL, HIGH, MEDIUM, LOW)
- All 29 unit tests pass covering directory structure, schema validation, module codes, and fixtures
- Schema includes exchange field for broker/streaming findings

### File List

- tests/live/audit/__init__.py (created)
- tests/live/audit/models.py (created)
- tests/live/audit/conftest.py (created)
- tests/live/audit/findings/__init__.py (created)
- tests/live/audit/findings/sample_findings.yaml (created)
- tests/live/audit/test_audit_infrastructure.py (created)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Story implemented - all ACs satisfied, 29 tests passing | Dev Agent |
