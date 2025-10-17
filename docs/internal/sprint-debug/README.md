# Sprint Debugging Guide

## Overview

This directory contains documentation and tracking for sprint debugging sessions focused on identifying and fixing issues in the RustyBT framework and documentation.

**Purpose:**
- Systematic identification and resolution of bugs, inconsistencies, and technical debt
- Comprehensive documentation validation and correction
- Code quality improvements and standards enforcement
- Performance issue identification and resolution

## Session Workflow

### 1. Session Initialization

Each debugging session should follow this structure:

1. **Review Current State**
   - Check `fixes.md` for recent fixes and patterns
   - Review `KNOWN_ISSUES.md` in `docs/internal/`
   - Identify focus areas (framework code, documentation, tests, etc.)

2. **Create Session Timestamp**
   - All fixes are batched and timestamped
   - Format: `YYYY-MM-DD HH:MM:SS`
   - Record in `fixes.md` before committing

### 2. ⚠️ MANDATORY Pre-Flight Checklist

**BEFORE starting ANY fix batch, complete the appropriate pre-flight checklist in `fixes.md`:**

#### For Documentation Updates:
- Verify content exists in source code
- Test ALL code examples
- Verify ALL API signatures match source
- Ensure realistic data (no "foo", "bar")
- Read quality standards
- Prepare testing environment

#### For Framework Code Updates:
- Understand code to be modified
- Review coding standards & zero-mock enforcement
- Plan testing strategy (NO MOCKS)
- Ensure complete type hints
- Verify testing environment works
- Complete impact analysis

**See `fixes.md` template for complete checklists. These are MANDATORY - no fixes without pre-flight completion.**

### 3. Debugging Process

#### Framework Debugging
- Run existing tests: `pytest tests/`
- Check linting: `ruff check rustybt/`
- Type checking: `mypy rustybt/ --strict`
- Review code for zero-mock violations
- Identify performance bottlenecks
- Check for security issues

#### Documentation Debugging
- Validate markdown syntax
- Check for broken links
- Verify code examples are executable
- Ensure consistency with coding standards
- Check for outdated information
- Validate API documentation matches implementation

### 4. Fix Documentation

For **each batch of fixes**, document in `fixes.md`:

```markdown
## [YYYY-MM-DD HH:MM:SS] - Batch Description

**Focus Area:** [Framework/Documentation/Tests/etc.]

**Issues Found:**
1. Issue description and location
2. Issue description and location
...

**Fixes Applied:**
1. Fix description and files modified
2. Fix description and files modified
...

**Tests Added/Modified:**
- List of test files changed
- New test coverage added

**Verification:**
- [ ] Tests pass
- [ ] Linting passes
- [ ] Type checking passes
- [ ] Documentation builds successfully
- [ ] No regressions introduced

**Files Modified:**
- `path/to/file1.py`
- `path/to/file2.md`
...

**Commit Hash:** [will be filled after commit]

---
```

### 5. Verification Checklist

Before committing any batch of fixes:

- [ ] **Pre-flight checklist completed** (in fixes.md batch entry)
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Linting clean: `ruff check rustybt/`
- [ ] Type checking passes: `mypy rustybt/ --strict`
- [ ] Black formatting: `black rustybt/ tests/ --check`
- [ ] No zero-mock violations: `scripts/detect_mocks.py`
- [ ] Documentation builds without warnings: `mkdocs build --strict`
- [ ] Git status clean (no unintended changes)
- [ ] Fix batch documented in `fixes.md` with completed checklist

### 6. Commit and Push

**Commit Message Format:**
```
fix(sprint-debug): [brief description of batch]

- Fix 1 summary
- Fix 2 summary
- Fix 3 summary

Refs: docs/internal/sprint-debug/fixes.md [timestamp]
```

**Process:**
1. Document fixes in `fixes.md` with timestamp
2. Stage all changes: `git add .`
3. Commit with descriptive message
4. Update `fixes.md` with commit hash
5. Push to remote: `git push origin [branch]`

## Directory Structure

```
sprint-debug/
├── README.md              # This file - session guide
├── fixes.md               # Chronological fix log
├── patterns.md            # Common issues and patterns (future)
└── metrics.md             # Sprint debugging metrics (future)
```

## Best Practices

### Issue Identification
- Use systematic scanning (don't rely on memory)
- Check related files when fixing one issue
- Look for patterns across similar code
- Validate assumptions with tests

### Fix Implementation
- One logical batch at a time (don't mix unrelated fixes)
- Write tests before or with fixes
- Update documentation when changing behavior
- Follow project coding standards strictly

### Documentation
- Be specific about what was wrong and why
- Include file paths and line numbers when relevant
- Note any side effects or related changes
- Record verification steps taken

### Quality Gates
- Never skip verification checklist
- Don't commit if tests fail (fix or skip flaky tests explicitly)
- Document any known limitations of fixes
- Update KNOWN_ISSUES.md if issues remain

## Common Fix Categories

1. **Code Quality**
   - Zero-mock violations
   - Type hint missing or incorrect
   - Unused imports
   - Complex functions needing refactor
   - Error handling improvements

2. **Documentation**
   - Typos and grammar
   - Outdated examples
   - Missing API documentation
   - Broken internal links
   - Inconsistent formatting

3. **Tests**
   - Missing test coverage
   - Flaky tests
   - Incorrect assertions
   - Missing edge cases
   - Test data issues

4. **Performance**
   - Inefficient algorithms
   - Unnecessary computations
   - Memory leaks
   - Database query optimization

5. **Security**
   - Hardcoded credentials
   - Input validation missing
   - SQL injection risks
   - Insecure defaults

## Metrics to Track

- Total issues found per session
- Issues fixed per batch
- Test coverage change
- Documentation coverage change
- Average fix time
- Regression count
- Code quality score improvement

## References

- Main project docs: `docs/`
- Architecture: `docs/internal/architecture/`
- Coding standards: `docs/internal/architecture/coding-standards.md`
- Zero-mock enforcement: `docs/internal/architecture/zero-mock-enforcement.md`
- Known issues: `docs/internal/KNOWN_ISSUES.md`

## Session Log

Track active and completed sessions:

| Date | Focus Area | Issues Found | Issues Fixed | Status |
|------|------------|--------------|--------------|--------|
| YYYY-MM-DD | TBD | TBD | TBD | In Progress |

---

**Last Updated:** 2025-10-17
**Maintained By:** Development Team
