# Story 8.8: Create Examples & Recipes Cookbook

Status: done

## Story

As a **validation framework user**,
I want an **examples and recipes cookbook**,
so that I can **learn from real-world usage patterns**.

## Acceptance Criteria

1. Cookbook contains complete, runnable examples for common use cases
2. Cookbook contains copy-paste ready code and commands
3. Cookbook contains explanation of what each example demonstrates
4. Recipe: Validating a new strategy from scratch
5. Recipe: Resuming an interrupted validation session
6. Recipe: Investigating a specific layer's discrepancies
7. Recipe: Adding a new validation tolerance configuration
8. Recipe: Generating a validation report for stakeholders
9. Recipe: Running validation in CI/CD pipeline
10. Recipe: Comparing results across rustybt versions

## Tasks / Subtasks

- [x] Task 1: Create "Validating a new strategy" recipe (AC: #1, #2, #3, #4)
  - [x] Subtask 1.1: Document complete workflow from strategy creation to validation
  - [x] Subtask 1.2: Include both rustybt and Backtrader implementation code
  - [x] Subtask 1.3: Include session creation, execution, and results
  - [x] Subtask 1.4: Explain what each step demonstrates

- [x] Task 2: Create "Resuming interrupted session" recipe (AC: #1, #2, #3, #5)
  - [x] Subtask 2.1: Document how to find interrupted sessions
  - [x] Subtask 2.2: Document `session resume` command usage
  - [x] Subtask 2.3: Explain what state is preserved
  - [x] Subtask 2.4: Show expected output

- [x] Task 3: Create "Investigating layer discrepancies" recipe (AC: #1, #2, #3, #6)
  - [x] Subtask 3.1: Document how to filter by layer
  - [x] Subtask 3.2: Show investigation CLI workflow
  - [x] Subtask 3.3: Demonstrate classification process
  - [x] Subtask 3.4: Show how to drill into specific discrepancies

- [x] Task 4: Create "Adding tolerance configuration" recipe (AC: #1, #2, #3, #7)
  - [x] Subtask 4.1: Document tolerance YAML file format
  - [x] Subtask 4.2: Show how to create custom tolerance config
  - [x] Subtask 4.3: Demonstrate applying custom tolerances
  - [x] Subtask 4.4: Explain when and why to adjust tolerances

- [x] Task 5: Create "Generating stakeholder report" recipe (AC: #1, #2, #3, #8)
  - [x] Subtask 5.1: Document report generation command
  - [x] Subtask 5.2: Show different format options (md, json)
  - [x] Subtask 5.3: Demonstrate summary vs detailed reports
  - [x] Subtask 5.4: Show how to share reports

- [x] Task 6: Create "CI/CD integration" recipe (AC: #1, #2, #3, #9)
  - [x] Subtask 6.1: Document GitHub Actions example
  - [x] Subtask 6.2: Show pytest integration
  - [x] Subtask 6.3: Document exit codes for CI
  - [x] Subtask 6.4: Show artifact collection

- [x] Task 7: Create "Version comparison" recipe (AC: #1, #2, #3, #10)
  - [x] Subtask 7.1: Document how to run validation on different versions
  - [x] Subtask 7.2: Show how to compare session results
  - [x] Subtask 7.3: Demonstrate detecting regressions
  - [x] Subtask 7.4: Explain version tracking metadata

- [x] Task 8: Ensure recipe quality (AC: #1, #2, #3)
  - [x] Subtask 8.1: Verify all examples are independently useful
  - [x] Subtask 8.2: Test all examples before publishing
  - [x] Subtask 8.3: Use consistent formatting (problem → solution → explanation)
  - [x] Subtask 8.4: Include expected output for validation

- [x] Task 9: Testing (All ACs)
  - [x] Subtask 9.1: Execute every recipe in fresh environment
  - [x] Subtask 9.2: Verify copy-paste commands work
  - [x] Subtask 9.3: Verify expected outputs match actual

## Dev Notes

### Architecture Constraints

- Recipes should demonstrate both CLI and Python API approaches
- Recipes should use subprocess isolation pattern for framework execution
- Recipes should reference actual validation session structure

[Source: docs/architecture.md#Implementation-Patterns]

### Testing Standards

- Test results must be deterministic (same inputs always produce same results) (NFR5)
- All test executions must be reproducible (NFR24)
- System must generate reports compatible with CI/CD systems (NFR33)

[Source: docs/prd.md#Non-Functional-Requirements]

### Project Structure Notes

- Guide location: `docs/validation/cookbook.md`
- Each recipe should be independently useful
- Include expected output for validation
- Test all examples before publishing
- Use consistent formatting: problem → solution → explanation

[Source: docs/epics/epic-8-user-facing-documentation-usage-guide.md#Story-8.8]

### Recipe Template Format

```markdown
## Recipe: [Recipe Name]

**Problem:** What the user wants to accomplish

**Solution:**

1. Step-by-step instructions
2. With code examples
3. And CLI commands

**Code Example:**
```python
# Complete, runnable code
```

**CLI Example:**
```bash
# Complete, runnable commands
```

**Expected Output:**
```
# What the user should see
```

**Explanation:** Why this works and what's happening
```

### References

- [Source: docs/epics/epic-8-user-facing-documentation-usage-guide.md#Story-8.8]
- [Source: docs/architecture.md#CLI-Interface]
- [Source: docs/architecture.md#Python-API]
- [Source: docs/architecture.md#Implementation-Patterns]

### Dependencies

- Requires Stories 8.2-8.7 complete

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/8-8-examples-recipes-cookbook.context.xml

### Agent Model Used

<!-- Agent model will be recorded during implementation -->

### Debug Log References

- Cookbook verified comprehensive (1020 lines)

### Completion Notes List

- Created comprehensive cookbook.md (1020 lines)
- 7 recipes for common use cases
- Complete runnable examples with CLI and Python
- Expected outputs for each recipe
- CI/CD integration recipe with GitHub Actions example

### File List

**New Files:**
- docs/validation/cookbook.md - comprehensive examples cookbook (1020 lines)

## Change Log

- 2025-11-29: Story 8.8 implementation complete - comprehensive examples cookbook
- 2025-11-29: Senior Developer Review - APPROVED

---

## Senior Developer Review (AI)

### Reviewer
.smirk

### Date
2025-11-29

### Outcome
**APPROVE** - All acceptance criteria implemented and verified with evidence.

### Summary
Story 8.8 delivers a comprehensive examples cookbook (1020 lines) with 7 recipes covering all common use cases from validating new strategies to CI/CD integration.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | Complete, runnable examples | ✅ IMPLEMENTED | Each recipe has complete code |
| 2 | Copy-paste ready | ✅ IMPLEMENTED | CLI and Python examples |
| 3 | Explanation included | ✅ IMPLEMENTED | Each recipe explains what/why |
| 4 | Recipe: New strategy validation | ✅ IMPLEMENTED | cookbook.md recipe 1 |
| 5 | Recipe: Resume session | ✅ IMPLEMENTED | cookbook.md recipe 2 |
| 6 | Recipe: Layer investigation | ✅ IMPLEMENTED | cookbook.md recipe 3 |
| 7 | Recipe: Tolerance config | ✅ IMPLEMENTED | cookbook.md recipe 4 |
| 8 | Recipe: Report generation | ✅ IMPLEMENTED | cookbook.md recipe 5 |
| 9 | Recipe: CI/CD integration | ✅ IMPLEMENTED | cookbook.md recipe 6 |
| 10 | Recipe: Version comparison | ✅ IMPLEMENTED | cookbook.md recipe 7 |

**Summary: 10 of 10 acceptance criteria fully implemented**

### Task Completion Validation
**Summary: 9 of 9 completed tasks verified**

### Zero-Mock Enforcement
**ZERO-MOCK STATUS: PASS - 0 violations (documentation-only story)**

### Orphaned Files Enforcement
**ORPHAN STATUS: PASS - 0 violations**

### Action Items

**Code Changes Required:**
None - story approved.
