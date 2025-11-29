# QA Review Guide for External User Issue Fixes

**Purpose**: Instructions for QA agents and reviewers on how to review fixes for external user-reported issues.

**Audience**: QA agents (AI or human), code reviewers, and anyone performing quality checks on bug fixes.

**Last Updated**: 2025-10-24

---

## Overview

External user issue fixes follow a lightweight review process. Unlike full epics/stories, these fixes:
- ❌ **Do NOT require** gate files (.gate-epic-review, .gate-story-review)
- ❌ **Do NOT require** full PRD/Architecture review process
- ✅ **Do require** focused QA review using this guide
- ✅ **Do require** verification of pre-flight checklist completion
- ✅ **Do require** testing and validation

**Review Goal**: Ensure the fix is correct, complete, and safe to merge without introducing regressions.

---

## Quick Reference

### Review Checklist (Use this for quick reviews)

```markdown
## QA Review Checklist

**Fix Information**:
- Branch: `fix/[timestamp]-[description]`
- Fix Document: `docs/internal/sprint-debug/fixes/completed/[timestamp]-[title].md`
- Reviewer: [Name/Agent]
- Review Date: [Date]

**Pre-Flight Verification**:
- [ ] Pre-flight checklist completed in fix document
- [ ] All pre-flight items checked as done
- [ ] No skipped pre-flight items without justification

**Fix Quality**:
- [ ] Issue correctly identified and understood
- [ ] Root cause analysis is accurate
- [ ] Fix addresses root cause (not just symptoms)
- [ ] All affected locations updated
- [ ] No unintended side effects

**Code Quality** (if applicable):
- [ ] Code follows coding standards
- [ ] Complete type hints present
- [ ] No mock violations (CR-002)
- [ ] Error handling appropriate
- [ ] Logging added where needed

**Documentation Quality** (if applicable):
- [ ] Examples are copy-paste executable
- [ ] API signatures verified against source
- [ ] No fabricated content
- [ ] Cross-references updated

**Testing**:
- [ ] All tests pass
- [ ] Linting clean
- [ ] Type checking passes
- [ ] Manual testing performed
- [ ] Coverage adequate (90%+ for code changes)

**Completeness**:
- [ ] Fix document fully completed
- [ ] Commit message descriptive
- [ ] Files modified list accurate
- [ ] Statistics filled in
- [ ] Notes section has important context

**Decision**:
- [ ] ✅ APPROVED - Merge to main
- [ ] ❌ CHANGES REQUESTED - See feedback below
- [ ] ⏸️  BLOCKED - Cannot proceed (explain)

**Feedback/Notes**:
[Your comments here]
```

---

## Detailed Review Process

### Step 1: Retrieve Fix Information

**Required information from developer**:
1. **Branch name**: `fix/[timestamp]-[brief-description]`
2. **Fix document path**: `docs/internal/sprint-debug/fixes/completed/[timestamp]-[title].md`

**Commands to get the fix**:
```bash
# Fetch latest branches
git fetch origin

# Checkout the fix branch
git checkout fix/[timestamp]-[brief-description]

# Read the fix document
cat docs/internal/sprint-debug/fixes/completed/[timestamp]-[title].md
```

---

### Step 2: Review Fix Document Structure

**Verify the fix document contains all required sections**:

**Required Sections**:
- ✅ Title with timestamp
- ✅ Commit/Focus Area/Severity metadata
- ✅ Pre-flight checklist (completed with [x])
- ✅ User-Reported Issue section
- ✅ Issues Found section
- ✅ Root Cause Analysis section
- ✅ Fixes Applied section
- ✅ Tests Added/Modified section
- ✅ Verification section (completed)
- ✅ Files Modified section
- ✅ Statistics section
- ✅ Commit Hash section
- ✅ Branch section
- ✅ Notes section

**Red Flags**:
- ❌ Missing pre-flight checklist
- ❌ Pre-flight checklist not completed (empty [ ] boxes)
- ❌ Verification checklist not completed
- ❌ Missing root cause analysis
- ❌ Empty statistics section

**If any red flags found**: Request developer complete the fix document before continuing review.

---

### Step 3: Verify Pre-Flight Checklist Completion

**For Documentation Fixes**:

Read the "For Documentation Updates: Pre-Flight Checklist" section and verify:

```markdown
✅ Content verified in source code
   ✅ Located source implementation with file:line reference
   ✅ Confirmed functionality exists
   ✅ Understand actual behavior

✅ Technical accuracy verified
   ✅ ALL code examples tested
   ✅ ALL API signatures match source
   ✅ ALL import paths work
   ✅ NO fabricated content

✅ Example quality verified
   ✅ Realistic data (not "foo", "bar")
   ✅ Copy-paste executable
   ✅ Best practices demonstrated
   ✅ Complex examples commented

✅ Quality standards compliance
   ✅ Read DOCUMENTATION_QUALITY_STANDARDS.md
   ✅ Read coding-standards.md
   ✅ Zero documentation debt commitment
   ✅ No syntax inference without verification

✅ Cross-references checked
   ✅ Related docs identified
   ✅ Outdated info checked
   ✅ Terminology consistent
   ✅ No broken links

✅ Testing preparation
   ✅ Testing environment ready
   ✅ Test data available
   ✅ Can validate docs build
```

**For Code Fixes**:

Read the "For Framework Code Updates: Pre-Flight Checklist" section and verify:

```markdown
✅ Understanding
   ✅ Understand code to be modified
   ✅ Reviewed related code
   ✅ Understand side effects

✅ Standards Review
   ✅ Read coding-standards.md
   ✅ Read zero-mock-enforcement.md
   ✅ Understand CR-002 requirements
   ✅ Understand CR-004 requirements

✅ Testing Strategy
   ✅ Tests planned before code (TDD)
   ✅ Tests use real implementations (NO MOCKS)
   ✅ Edge cases covered
   ✅ Target 90%+ coverage

✅ Type Safety
   ✅ Complete type hints planned
   ✅ mypy --strict compliance planned
   ✅ Error handling planned

✅ Environment Ready
   ✅ Testing environment works
   ✅ Linting works
   ✅ Type checking works

✅ Impact Analysis
   ✅ Affected components identified
   ✅ Breaking changes checked
   ✅ Backward compatibility planned
```

**If pre-flight incomplete**: ❌ **REJECT** - Request developer complete pre-flight checklist.

---

### Step 4: Review Root Cause Analysis

**Evaluate the root cause analysis**:

**Good root cause analysis answers**:
1. ✅ **Why did this issue occur?** (Primary cause + contributing factors)
2. ✅ **What systemic issue allowed it?** (Process gap, missing validation, etc.)
3. ✅ **How do we prevent recurrence?** (Concrete prevention mechanisms)

**Example of good root cause analysis**:
```markdown
## Root Cause Analysis

**Why did this issue occur:**
1. Documentation written with hardcoded dates (2020-2023) - valid at time
2. Bundle later updated to dynamic dates (last 2 years)
3. Documentation never updated to reflect change
4. No validation to catch date range mismatches

**What pattern should prevent recurrence:**
1. Use relative dates in documentation (e.g., "last year of data")
2. Add CLI command to show available date ranges
3. Create script to test all code examples in docs
4. Add pre-commit check for hardcoded dates
```

**Red flags**:
- ❌ "I don't know why this happened"
- ❌ Missing "what pattern should prevent recurrence"
- ❌ Surface-level analysis (doesn't identify systemic issue)
- ❌ No prevention mechanisms proposed

**If root cause weak**: Request deeper analysis before approval.

---

### Step 5: Verify Fix Completeness

**Check "Fixes Applied" section**:

For each fix, verify:
- ✅ File path and line numbers provided
- ✅ Clear description of what changed
- ✅ Logical and addresses root cause
- ✅ No "TODO" or incomplete work

**Check "Files Modified" section**:

```bash
# Compare documented files with actual changes
git diff main --name-only

# Should match the "Files Modified" list in fix document
```

**Verify all occurrences fixed**:

For documentation fixes, check if issue exists elsewhere:
```bash
# Example: If fixing date "2020-01-01", search for other occurrences
grep -r "2020-01-01" docs/

# If found, verify developer noted this or fixed all
```

**Red flags**:
- ❌ Modified files don't match fix document
- ❌ Partial fix (some occurrences left unfixed)
- ❌ Unrelated changes in commit
- ❌ TODOs or incomplete work

---

### Step 6: Review Code/Documentation Changes

**For Documentation Fixes**:

1. **Read the changed documentation**:
   ```bash
   git diff main -- docs/
   ```

2. **Verify examples are executable**:
   - Copy code examples
   - Paste into test environment
   - Run and verify they work

3. **Check API signatures**:
   - Find documented function signatures
   - Compare with source code
   - Ensure they match exactly

4. **Check for fabricated content**:
   - Look for suspicious function names
   - Look for made-up parameters
   - Verify everything exists in codebase

**For Code Fixes**:

1. **Review code quality**:
   ```bash
   # Check the changes
   git diff main
   ```

2. **Verify type hints**:
   - All parameters have type hints
   - Return types specified
   - Python 3.12+ syntax used

3. **Check for mocks**:
   ```bash
   # Search for mock violations in changed files
   git diff main | grep -i "mock\|patch\|stub"
   ```
   - Should find ZERO results in test files

4. **Review error handling**:
   - Appropriate try-except blocks
   - Meaningful error messages
   - Proper logging

---

### Step 7: Execute Verification Commands

**Run the verification checklist commands**:

```bash
# 1. Run tests
pytest tests/ -v

# 2. Check linting
ruff check rustybt/

# 3. Type checking
mypy rustybt/ --strict

# 4. Black formatting
black rustybt/ tests/ --check

# 5. Check for mocks (if code changes)
# (Manual grep or script)
grep -r "mock\|patch" tests/

# 6. Documentation build (if doc changes)
mkdocs build --strict
```

**Expected results**:
- ✅ All tests pass
- ✅ Zero linting errors
- ✅ Zero type errors (minor warnings ok)
- ✅ Black formatting clean
- ✅ Zero mocks found
- ✅ Docs build successfully

**If any verification fails**: ❌ **REJECT** - Request developer fix verification issues.

---

### Step 8: Manual Testing

**For Documentation Fixes**:

1. **Test code examples**:
   - Copy first code example from docs
   - Create new Python file or notebook
   - Paste and run
   - Verify it works as documented

2. **Test at least 2-3 examples** if multiple exist

3. **Check cross-references**:
   - Click any links in documentation
   - Verify they resolve correctly

**For Code Fixes**:

1. **Test the specific bug scenario**:
   - Read "User-Reported Issue" section
   - Recreate user's exact scenario
   - Verify fix resolves the issue

2. **Test edge cases**:
   - Think of related scenarios
   - Test boundary conditions
   - Verify no regressions

3. **Check performance** (if relevant):
   - Time operations if performance-sensitive
   - Verify no significant slowdown

---

### Step 9: Review Test Coverage (Code Fixes Only)

**If code was changed, check test coverage**:

```bash
# Run tests with coverage
pytest tests/ --cov=rustybt --cov-report=term-missing
```

**Evaluate coverage**:
- ✅ **90%+ coverage**: Excellent
- ✅ **75-89% coverage**: Good (acceptable for CR-002 compliant code)
- ⚠️  **60-74% coverage**: Marginal (review why coverage is low)
- ❌ **<60% coverage**: Insufficient (request more tests)

**Coverage exceptions** (acceptable reasons for <90%):
- Defensive error handling (hard to trigger)
- Jupyter notebook detection (requires real Jupyter)
- Platform-specific code
- Deprecated code paths

**Check "Tests Added/Modified" section**:
- Verify tests were actually added
- Check tests follow TDD approach
- Verify zero-mock compliance

---

### Step 10: Review Commit & Metadata

**Check commit message**:
```bash
git log -1 --pretty=full
```

**Good commit message format**:
```
fix(docs): Brief description of fix

- Fix 1 summary
- Fix 2 summary
- Fix 3 summary

Refs: docs/internal/sprint-debug/fixes/[timestamp]-[title].md
```

**Verify**:
- ✅ Follows conventional commit format: `fix(scope): description`
- ✅ Brief but descriptive
- ✅ References fix document
- ✅ Lists key changes

**Check fix document metadata**:
- ✅ Commit hash filled in
- ✅ Branch name correct
- ✅ Statistics filled in
- ✅ Notes section has context

---

### Step 11: Make Review Decision

**Three possible outcomes**:

#### ✅ APPROVED

**Criteria**:
- All pre-flight items completed
- Root cause analysis solid
- Fix is complete and correct
- All verification checks pass
- Manual testing successful
- No red flags identified

**Action**:
```markdown
## QA Review

**Reviewer**: [Your name/agent]
**Review Date**: [Date]
**Status**: ✅ APPROVED

**Summary**:
Fix is complete, well-documented, and tested. All verification checks pass.

**Notes**:
- [Any positive observations]
- [Suggestions for future improvements]

**Approval**: Ready to merge to main.
```

**Add this to the fix document** and notify developer to proceed with merge.

---

#### ❌ CHANGES REQUESTED

**Criteria**:
- Fix is mostly good but needs adjustments
- Minor issues found
- Verification checks failed
- Incomplete documentation
- Missing test coverage

**Action**:
```markdown
## QA Review

**Reviewer**: [Your name/agent]
**Review Date**: [Date]
**Status**: ❌ CHANGES REQUESTED

**Issues Found**:

1. **[Issue category]**
   - Problem: [Description]
   - Location: [File:line or section]
   - Required action: [What needs to be fixed]

2. **[Another issue]**
   - Problem: [Description]
   - Required action: [What needs to be fixed]

**Required Changes**:
- [ ] Fix issue 1
- [ ] Fix issue 2
- [ ] Re-run verification checks
- [ ] Update fix document with new commit hash

**Once addressed, request re-review**.
```

**Add this to fix document** and notify developer of required changes.

---

#### ⏸️ BLOCKED

**Criteria**:
- Fundamental issue with fix approach
- Introduces regressions
- Violates constitutional requirements
- Requires architectural discussion
- **Requires 3+ separate stories** (needs epic creation and breakdown)

**Action**:
```markdown
## QA Review

**Reviewer**: [Your name/agent]
**Review Date**: [Date]
**Status**: ⏸️ BLOCKED

**Blocking Issues**:

1. **[Blocking reason]**
   - Description: [What's wrong]
   - Impact: [Why this blocks merge]
   - Recommendation: [What should happen instead]

**Recommended Path Forward**:
[Escalate to epic / Architectural review / Major refactor / etc.]

**This fix cannot proceed as-is**.
```

**Add this to fix document** and discuss with developer/team.

---

## Review Templates

### Template: Approved Review

Add this section to the fix document:

```markdown
---

## QA Review

**Reviewer**: [Name/Agent]
**Review Date**: 2025-MM-DD
**Status**: ✅ APPROVED

**Pre-Flight Verification**:
- [x] Pre-flight checklist completed
- [x] All items checked and justified

**Fix Quality Review**:
- [x] Issue correctly identified
- [x] Root cause analysis accurate
- [x] Fix addresses root cause
- [x] All occurrences updated
- [x] No unintended side effects

**Code/Documentation Quality**:
- [x] Follows project standards
- [x] Type hints complete (if code)
- [x] No mock violations (if code)
- [x] Examples executable (if docs)
- [x] API signatures verified (if docs)

**Testing Verification**:
- [x] All tests pass (pytest)
- [x] Linting clean (ruff)
- [x] Type checking passes (mypy)
- [x] Manual testing successful
- [x] Coverage adequate: [X%]

**Completeness**:
- [x] Fix document complete
- [x] Commit message descriptive
- [x] Metadata filled in

**Summary**:
Fix is complete, well-documented, and thoroughly tested. [Add specific positive observations]

**Approval**: ✅ Ready to merge to main

---
```

---

### Template: Changes Requested Review

Add this section to the fix document:

```markdown
---

## QA Review

**Reviewer**: [Name/Agent]
**Review Date**: 2025-MM-DD
**Status**: ❌ CHANGES REQUESTED

**Issues Found**:

### Issue 1: [Category]
**Problem**: [Clear description of what's wrong]
**Location**: [File:line or section of fix document]
**Required Action**: [Specific steps to fix]
**Severity**: [CRITICAL / MEDIUM / LOW]

### Issue 2: [Category]
**Problem**: [Description]
**Location**: [File:line]
**Required Action**: [Specific steps]
**Severity**: [CRITICAL / MEDIUM / LOW]

**Required Changes Checklist**:
- [ ] Address Issue 1
- [ ] Address Issue 2
- [ ] Re-run verification checks (all must pass)
- [ ] Update fix document with new commit hash
- [ ] Request re-review

**Notes**:
[Additional context or suggestions]

**Next Steps**: Address above issues and push updated commit to branch. Request re-review when ready.

---
```

---

### Template: Blocked Review

Add this section to the fix document:

```markdown
---

## QA Review

**Reviewer**: [Name/Agent]
**Review Date**: 2025-MM-DD
**Status**: ⏸️ BLOCKED

**Blocking Issues**:

### Blocker 1: [Issue]
**Description**: [What's fundamentally wrong]
**Impact**: [Why this prevents merge]
**Constitutional Violation**: [If applicable: CR-XXX]

### Blocker 2: [Issue]
**Description**: [What's wrong]
**Impact**: [Why this prevents merge]

**Recommended Path Forward**:

[One of:]
- Escalate to full epic using `/pm` agent
- Requires architectural review and discussion
- Scope too large - break into multiple fixes
- Approach fundamentally flawed - needs redesign
- Violates project constitution - requires exception or different approach

**This fix cannot proceed in its current form**.

**Action Required**: [Specific recommendation]

---
```

---

## AI Agent Guidelines

**If you are a QA agent (AI) performing review**:

### Execution Instructions:

1. **Read this entire guide** before starting review
2. **Follow steps 1-11 sequentially** - do not skip
3. **Document your findings** as you go
4. **Be thorough** - sprint fixes can be substantial; review depth should match fix complexity
5. **Use templates** provided above
6. **Be specific** in feedback - reference file:line when possible
7. **Test examples** manually - don't assume they work

### Decision-Making:

- **When to approve**: All checks pass, no red flags, confident in quality
- **When to request changes**: Minor issues, fixable quickly, clear guidance provided
- **When to block**: Fundamental issues, constitutional violations, requires 3+ separate stories

### Communication:

- **Be clear and specific**: "Line 42 missing type hint for parameter 'data'" not "some type hints missing"
- **Be helpful**: Suggest solutions, not just point out problems
- **Be respectful**: Acknowledge good work while noting improvements needed
- **Reference standards**: Cite CR-002, coding-standards.md, etc. when relevant

### Efficiency:

- Run verification commands in parallel when possible
- Read fix document first to understand scope
- Focus review on changed files
- Don't re-review unchanged code

### Red Lines (Always Reject):

- ❌ Pre-flight checklist not completed
- ❌ Mocks used in tests (CR-002 violation)
- ❌ Missing type hints (CR-004 violation)
- ❌ Fabricated API documentation
- ❌ Verification checks failing
- ❌ Introduces regressions

---

## Differences from Epic/Story QA

**External user issue fixes are DIFFERENT from epics/stories**:

| Aspect | Epic/Story QA | Issue Fix QA |
|--------|---------------|--------------|
| Gate files | Required (.gate-epic-review) | NOT required |
| PRD review | Required | NOT required |
| Architecture review | Required | NOT required |
| Scope | Multi-story (3+) | Single cohesive fix |
| Review depth | Deep, comprehensive | Focused, targeted |
| Complexity | Any | Any (as long as single fix) |
| Approval process | Multi-stage | Single review |
| Documentation | Full PRD + Architecture | Fix document only |

**Key principle**: Sprint fixes are for single cohesive changes (even if substantial). Escalate only when work requires 3+ separate stories.

---

## FAQ

**Q: What if the fix is larger than expected?**
**A**: Size/complexity alone is NOT a reason to escalate. Only BLOCK and escalate if the fix requires 3+ separate stories to implement. A large but cohesive single fix is acceptable for sprint workflow.

**Q: What if I'm not sure if fix is correct?**
**A**: Request changes and ask developer to provide more context, testing evidence, or justification.

**Q: What if documentation examples don't work?**
**A**: REJECT immediately. Examples MUST be copy-paste executable. This is non-negotiable.

**Q: What if code uses mocks?**
**A**: REJECT immediately. Mocks violate CR-002 (Zero-Mock Enforcement). No exceptions for external user fixes.

**Q: Can I approve if coverage is only 70%?**
**A**: Yes, if:
- Missing coverage is defensive error handling or platform-specific
- Code follows CR-002 (real implementations, no mocks)
- Core functionality has near-100% coverage
Otherwise, request more tests.

**Q: How much manual testing is enough?**
**A**: At minimum:
- Test the exact user scenario from "User-Reported Issue"
- Test 2-3 code examples (if documentation)
- Test one edge case (if code)

**Q: What if fix document is incomplete?**
**A**: Request developer complete it before continuing review. Incomplete fix documents make review impossible.

---

## References

- **Main Workflow**: `EXTERNAL-USER-ISSUE-WORKFLOW.md` (developer guide)
- **Sprint Debug Guide**: `README.md`
- **Coding Standards**: `docs/internal/architecture/coding-standards.md`
- **Zero-Mock Enforcement**: `docs/internal/architecture/zero-mock-enforcement.md`
- **Documentation Standards**: `docs/internal/architecture/DOCUMENTATION_QUALITY_STANDARDS.md`
- **Project Constitution**: `docs/internal/architecture/constitution.md`

---

**Version History**:
- 2025-10-24: Initial version created for external user issue fix reviews
- 2025-10-24: Updated escalation criteria - focus on "3+ stories" not time/complexity
