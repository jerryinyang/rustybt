# External User Issue Handling Workflow

**Purpose**: Step-by-step instruction manual for developers and AI agents on how to handle issues reported by external users during testing and usage of the rustybt framework.

**Audience**: Human developers, AI agents (like Claude Code), and anyone handling bug reports from external users.

**Last Updated**: 2025-10-24

---

## Overview

When external users test rustybt in different environments, they may encounter:
- Installation problems
- Documentation gaps or errors
- API inconsistencies
- Missing features
- Confusing error messages
- Performance issues

This guide provides a systematic workflow to handle these issues from discovery through resolution.

---

## Quick Decision Tree

```
Issue Discovered
    ↓
Is this a CRITICAL blocker?
    YES → Follow "Critical Issue Fast Track" below
    NO  → Continue to standard workflow
    ↓
Does it require code changes?
    YES → Follow "Framework Code Fix Workflow"
    NO  → Is it documentation?
        YES → Follow "Documentation Fix Workflow"
        NO  → Follow "Other Issues" workflow
```

---

## Critical Issue Fast Track

**Use when**: Issue blocks new users, causes data corruption, or breaks core functionality.

**Example**: Quick Start guide contains incorrect dates that cause 100% failure rate.

### Fast Track Steps:

1. **Immediate Assessment**
   - Confirm issue severity
   - Verify reproducibility
   - Check if workaround exists

2. **Create Fix Branch**
   ```bash
   # Branch naming: fix/YYYYMMDD-HHMMSS-brief-description
   TIMESTAMP=$(date +%Y%m%d-%H%M%S)
   git checkout -b "fix/${TIMESTAMP}-[brief-description]"
   ```

3. **Create Fix Document**
   ```bash
   cd docs/internal/sprint-debug/fixes/
   cp active-session.md "completed/$(date +%Y-%m-%d-%H%M%S)-critical-[brief-title].md"
   ```

4. **Complete Mandatory Pre-Flight** (see section below)

5. **Implement Fix**

6. **Verify & Commit**
   - Run verification checklist
   - Commit with descriptive message
   - Update fix document with commit hash
   - Push branch: `git push -u origin fix/${TIMESTAMP}-[brief-description]`

7. **QA Review** (see QA Review Guide)
   - Request review using QA agent or manual review
   - Address feedback if needed
   - Get approval

8. **Merge & Cleanup**
   ```bash
   git checkout main
   git merge fix/${TIMESTAMP}-[brief-description]
   git push origin main
   git branch -d fix/${TIMESTAMP}-[brief-description]
   git push origin --delete fix/${TIMESTAMP}-[brief-description]
   ```

9. **Document for Users**
   - Update KNOWN_ISSUES.md if needed
   - Consider release note if deployed

---

## Standard Workflow: Documentation Fixes

### Step 1: Issue Discovery & Branch Creation

**When you discover an issue** (via error message, confusion, or testing):

1. **Create fix branch** (MANDATORY):
   ```bash
   # Branch naming: fix/YYYYMMDD-HHMMSS-brief-description
   TIMESTAMP=$(date +%Y%m%d-%H%M%S)
   git checkout -b "fix/${TIMESTAMP}-[brief-description]"

   # Example: fix/20251024-143000-quickstart-date-mismatch
   ```

2. **Capture the context immediately**:
   ```markdown
   ## User-Reported Issue
   **User Error**: [exact error message or confusion]
   **User Scenario**: [what they were trying to do]
   **Expected Behavior**: [what should have happened]
   **Actual Behavior**: [what actually happened]
   **Impact**: [who/how many users affected]
   ```

3. **Create timestamped fix document**:
   ```bash
   # Format: YYYY-MM-DD-HHMMSS-brief-description.md
   cd docs/internal/sprint-debug/fixes/
   TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
   touch "completed/${TIMESTAMP}-[brief-title].md"
   ```

### Step 2: Mandatory Pre-Flight Checklist

**CRITICAL**: You MUST complete this checklist BEFORE making any changes.

**For Documentation Updates, verify**:
- [ ] **Content exists in source code**
  - [ ] Located source implementation (file:line)
  - [ ] Confirmed functionality exists as documented
  - [ ] Understand actual behavior
- [ ] **Technical accuracy verified**
  - [ ] ALL code examples tested and working
  - [ ] ALL API signatures match source code exactly
  - [ ] ALL import paths tested and working
  - [ ] NO fabricated content
- [ ] **Example quality verified**
  - [ ] Examples use realistic data (not "foo", "bar")
  - [ ] Examples are copy-paste executable
  - [ ] Examples demonstrate best practices
  - [ ] Complex examples include explanatory comments
- [ ] **Quality standards compliance**
  - [ ] Read `docs/internal/architecture/DOCUMENTATION_QUALITY_STANDARDS.md`
  - [ ] Read `docs/internal/architecture/coding-standards.md`
  - [ ] Commit to zero documentation debt
  - [ ] Will NOT use syntax inference without verification
- [ ] **Cross-references checked**
  - [ ] Identified related documentation to update
  - [ ] Checked for outdated information
  - [ ] Verified terminology consistency
  - [ ] No broken links
- [ ] **Testing preparation**
  - [ ] Testing environment ready
  - [ ] Test data available and realistic
  - [ ] Can validate documentation builds: `mkdocs build --strict`

**Document completion in your fix file**:
```markdown
## ⚠️ MANDATORY PRE-FLIGHT CHECKLIST

### For Documentation Updates: Pre-Flight Checklist

- [x] Content verified in source code
  - [x] Located source implementation: `file.py:line`
  ...
[Copy full checklist from active-session.md template]
```

### Step 3: Root Cause Analysis

**Understand WHY the issue occurred**:

```markdown
## Root Cause Analysis

**Why did this issue occur:**
1. [Primary cause]
2. [Contributing factors]
3. [Systemic issues]

**What pattern should prevent recurrence:**
1. [Prevention mechanism 1]
2. [Prevention mechanism 2]
3. [Process improvement]
```

**Example**:
```markdown
**Why did this issue occur:**
1. Documentation written with hardcoded dates (2020-2023)
2. Bundle updated to dynamic dates (last 2 years)
3. Documentation never updated to reflect change
4. No validation to catch date range mismatches

**What pattern should prevent recurrence:**
1. Use relative dates in documentation
2. Add CLI command to show available date ranges
3. Create script to test all code examples
4. Add pre-commit check for hardcoded dates
```

### Step 4: Implement Fixes

**Apply fixes systematically**:

```markdown
## Fixes Applied

**1. Fixed [Component Name]** - `path/to/file.ext:lines`
- Changed [what was wrong]
- Updated [specific change]
- Added [new content if applicable]
- Verified [how you tested it]

**2. Fixed [Another Component]** - `path/to/other/file.ext:lines`
...
```

**Best Practices**:
- Fix one logical issue at a time
- Update ALL occurrences (use grep to find them)
- Test each fix immediately
- Document file paths and line numbers

### Step 5: Verification Checklist

**Before committing, verify**:

```markdown
## Verification

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Linting clean: `ruff check rustybt/`
- [ ] Type checking passes: `mypy rustybt/ --strict`
- [ ] Black formatting: `black rustybt/ tests/ --check`
- [ ] Documentation builds: `mkdocs build --strict`
- [ ] No zero-mock violations: `scripts/detect_mocks.py`
- [ ] Manual testing completed with realistic data
- [ ] Git status clean (no unintended changes)
- [ ] Pre-flight checklist completed above
```

**For documentation-only changes**, mark code checks as N/A:
```markdown
- [x] All tests pass (N/A - no code changes)
- [x] Linting passes (N/A - no code changes)
...
```

### Step 6: Commit & Push Branch

**Create descriptive commit**:
```bash
git add .
git commit -m "fix(docs): [brief description]

- Fix 1 summary
- Fix 2 summary
- Fix 3 summary

Refs: docs/internal/sprint-debug/fixes/[timestamp]-[title].md"

# Push to remote for review
git push -u origin fix/[timestamp]-[brief-description]
```

**Update fix document with metadata**:
```markdown
## Commit Hash
`abc1234`

## Branch
`fix/[timestamp]-[brief-description]`

## Files Modified
- `path/to/file1.ext` - [what changed]
- `path/to/file2.ext` - [what changed]

## Statistics
- Issues found: X
- Issues fixed: Y
- Tests added: Z
- Lines changed: +X/-Y (net: +Z lines)

## Notes
- [Important context]
- [Follow-up needed]
- [User impact assessment]
```

### Step 7: Request QA Review

**Initiate review** (see `QA-REVIEW-GUIDE.md` for details):
```bash
# Option 1: Use QA agent (recommended)
# Provide QA agent with:
# - Branch name: fix/[timestamp]-[brief-description]
# - Fix document path: docs/internal/sprint-debug/fixes/completed/[timestamp]-[title].md

# Option 2: Manual review
# Tag reviewer or self-review using QA checklist
```

**Review outcome**:
- ✅ **Approved**: Proceed to Step 8 (merge)
- ❌ **Changes requested**: Address feedback, update commit, push again, repeat Step 7

### Step 8: Merge & Cleanup

**After QA approval**:
```bash
# Switch to main branch
git checkout main

# Merge fix branch
git merge fix/[timestamp]-[brief-description]

# Push merged changes
git push origin main

# Delete local branch
git branch -d fix/[timestamp]-[brief-description]

# Delete remote branch
git push origin --delete fix/[timestamp]-[brief-description]
```

**Update fix document**:
```markdown
## Merge Status
✅ Merged to main on [date]
Branch deleted: fix/[timestamp]-[brief-description]
```

### Step 9: Update Index

**Add entry to fixes/index.md**:
```bash
# Update table of contents with link to your new fix document
```

---

## Standard Workflow: Framework Code Fixes

### Step 1-2: Same as Documentation Workflow

Follow Steps 1-3 above to:
1. Create fix branch (MANDATORY)
2. Capture context
3. Create fix document

### Step 3: Mandatory Pre-Flight Checklist (Code)

**For Framework Code Updates, verify**:
- [ ] **Understanding**
  - [ ] Understand code to be modified (file:line)
  - [ ] Reviewed related code and dependencies
  - [ ] Understand side effects and impact
- [ ] **Standards Review**
  - [ ] Read `docs/internal/architecture/coding-standards.md`
  - [ ] Read `docs/internal/architecture/zero-mock-enforcement.md`
  - [ ] Understand CR-002 (Zero-Mock) requirements
  - [ ] Understand CR-004 (Type Safety) requirements
- [ ] **Testing Strategy**
  - [ ] Plan tests BEFORE writing code (TDD)
  - [ ] Tests use real implementations (NO MOCKS)
  - [ ] Tests cover edge cases and errors
  - [ ] Target 90%+ code coverage
- [ ] **Type Safety**
  - [ ] Plan complete type hints (Python 3.12+ syntax)
  - [ ] Plan mypy --strict compliance
  - [ ] Plan proper error handling
- [ ] **Environment Ready**
  - [ ] Testing environment works: `pytest tests/`
  - [ ] Linting works: `ruff check rustybt/`
  - [ ] Type checking works: `mypy rustybt/ --strict`
- [ ] **Impact Analysis**
  - [ ] Identified all affected components
  - [ ] Checked for breaking changes
  - [ ] Planned backward compatibility if needed

### Step 4: Test-Driven Development

**Write tests FIRST** (following TDD):

```markdown
## Tests Added/Modified

**Created test file**: `tests/path/to/test_feature.py`

**Test Cases**:
1. `test_[scenario_1]` - [what it tests]
2. `test_[scenario_2]` - [what it tests]
3. `test_[error_case]` - [what it tests]

**Coverage Target**: 90%+

**Zero-Mock Compliance**:
- Uses real filesystem operations
- Uses real introspection
- No mocking frameworks
```

### Step 5: Implementation

**Implement fix with**:
- Complete type hints (Python 3.12+)
- Google-style docstrings
- Error handling
- Logging (structured)
- No mocks (CR-002)

```markdown
## Fixes Applied

**1. Modified `rustybt/path/to/module.py`**
- Added function `new_function()` (lines X-Y)
- Modified function `existing_function()` (lines A-B)
- Added error handling for [case]
- Added type hints for all parameters

**2. Updated `rustybt/path/to/other.py`**
...
```

### Step 6-9: Verification, Commit, Review & Merge

Same as documentation workflow Steps 6-9, but ensure ALL checks pass (no N/A for code changes).

**Required for code changes**:
- ✅ All tests pass
- ✅ Linting clean
- ✅ Type checking passes
- ✅ No mock violations
- ✅ 90%+ coverage (if possible)

**Then follow**:
- Step 6: Commit & push branch
- Step 7: Request QA review
- Step 8: Merge & cleanup (after approval)
- Step 9: Update index

---

## Integration with Existing Sprint-Debug Structure

### Directory Structure
```
docs/internal/sprint-debug/
├── README.md                              # Main session guide
├── EXTERNAL-USER-ISSUE-WORKFLOW.md        # This file (you are here)
└── fixes/
    ├── index.md                           # Table of contents
    ├── active-session.md                  # Current feature development
    ├── completed/
    │   ├── 2025-10-24-HHMMSS-[title].md  # Your completed fixes
    │   └── ...
    ├── fix-history.md                     # Historical overview
    ├── common-issues-patterns.md          # Pattern library
    └── summary-statistics.md              # Metrics tracking
```

### When to Use Each Document

| Situation | Document to Use |
|-----------|----------------|
| Starting new feature work | `fixes/active-session.md` |
| External user reports bug | Create `completed/[timestamp]-[title].md` |
| Documentation gap found | Create `completed/[timestamp]-[title].md` |
| Performance issue | Create `completed/[timestamp]-[title].md` |
| Reviewing past fixes | `fixes/fix-history.md` or `fixes/index.md` |
| Looking for patterns | `fixes/common-issues-patterns.md` |
| Checking metrics | `fixes/summary-statistics.md` |
| Need workflow instructions | `EXTERNAL-USER-ISSUE-WORKFLOW.md` (this file) |

**Rule of Thumb**:
- **Active feature development**: Use `active-session.md` (tracks work over days/weeks)
- **Bug fixes and issues**: Create new timestamped file in `completed/` (immediate fix)

---

## Templates

### Template: Documentation Fix Document

```markdown
# [YYYY-MM-DD HH:MM:SS] - [Brief Title]

**Commit:** [Pending]
**Focus Area:** Documentation ([Severity Level])
**Severity:** [🔴 CRITICAL | 🟡 MEDIUM | 🟢 LOW]

---

## ⚠️ MANDATORY PRE-FLIGHT CHECKLIST

### For Documentation Updates: Pre-Flight Checklist

- [ ] **Content verified in source code**
  - [ ] Located source implementation: `file.py:line`
  - [ ] Confirmed functionality exists as documented
  - [ ] Understand actual behavior

[Continue with full checklist from active-session.md]

**Documentation Pre-Flight Complete**: [ ] YES [ ] NO

---

## User-Reported Issue

**User Error:**
```
[Exact error message or confusion]
```

**User Scenario:**
[What user was trying to do]

**Result:** [What happened]

---

## Issues Found

**Issue 1: [Title]** - `file:line`
[Description]

**Issue 2: [Title]** - `file:line`
[Description]

---

## Root Cause Analysis

**Why did this issue occur:**
1. [Cause 1]
2. [Cause 2]

**What pattern should prevent recurrence:**
1. [Prevention 1]
2. [Prevention 2]

---

## Fixes Applied

**1. Fixed [Component]** - `path/to/file:lines`
- [Change 1]
- [Change 2]

---

## Tests Added/Modified

- [Test file changes or N/A]

---

## Documentation Updated

- `path/to/doc1.md` - [What changed]
- `path/to/doc2.md` - [What changed]

---

## Verification

- [ ] All tests pass (or N/A)
- [ ] Linting passes (or N/A)
- [ ] Type checking passes (or N/A)
- [ ] Documentation builds: `mkdocs build --strict`
- [ ] Manual testing completed
- [ ] Pre-flight checklist completed above

---

## Files Modified

- `path/to/file1.ext` - [Description]
- `path/to/file2.ext` - [Description]

---

## Statistics

- Issues found: X
- Issues fixed: Y
- Tests added: Z
- Lines changed: +A/-B (net: +C lines)

---

## Commit Hash

`[commit hash]`

---

## Branch

`[branch name]`

---

## Notes

- [Important context]
- [User impact]
- [Follow-up needed]

---
```

### Template: Framework Code Fix Document

```markdown
# [YYYY-MM-DD HH:MM:SS] - [Brief Title]

**Commit:** [Pending]
**Focus Area:** Framework - [Component]
**Severity:** [🔴 CRITICAL | 🟡 MEDIUM | 🟢 LOW]

---

## ⚠️ MANDATORY PRE-FLIGHT CHECKLIST

### For Framework Code Updates: Pre-Flight Checklist

- [ ] **Understanding**
  - [ ] Understand code to be modified: `file.py:line`
  - [ ] Reviewed related code
  - [ ] Understand side effects

[Continue with full code checklist]

**Code Pre-Flight Complete**: [ ] YES [ ] NO

---

## User-Reported Issue

[Same as documentation template]

---

## Issues Found

[Same format as above]

---

## Root Cause Analysis

[Same format as above]

---

## Tests Added/Modified

**Created test file**: `tests/path/to/test_feature.py`

**Test Cases**:
1. `test_case_1` - [Description]
2. `test_case_2` - [Description]

**Zero-Mock Compliance**:
- [How tests follow CR-002]

**Coverage**: X% achieved

---

## Fixes Applied

**1. Modified `rustybt/path/to/file.py`**
- Added/Modified function `func()` (lines X-Y)
- Added type hints
- Added error handling

---

## Verification

- [x] All tests pass: `pytest tests/ -v`
- [x] Linting clean: `ruff check rustybt/`
- [x] Type checking passes: `mypy rustybt/ --strict`
- [x] Black formatting: `black rustybt/ tests/ --check`
- [x] No zero-mock violations
- [x] Coverage: X% (target: 90%)
- [x] Pre-flight checklist completed

---

## Files Modified

[Same as documentation template]

---

## Statistics

[Same as documentation template]

---

## Commit Hash

`[hash]`

---

## Notes

[Same as documentation template]

---
```

---

## Common Scenarios

### Scenario 1: User Reports Confusing Error Message

**Workflow**:
1. Capture exact error and context
2. Create fix document: `completed/[timestamp]-improve-error-message-[component].md`
3. Complete **code** pre-flight checklist
4. Write test that reproduces confusing error
5. Improve error message in code
6. Add helpful suggestions to error message
7. Update documentation if error is expected in some cases
8. Verify & commit

**Example**: User gets `LookupError: 2020-01-02 is not in DatetimeIndex[...]`
- **Better error**: "Date 2020-01-02 is outside bundle's available range (2023-10-18 to 2026-10-16). Run 'rustybt bundles --list' to see available dates."

### Scenario 2: User Can't Install Package

**Workflow**:
1. Capture installation command and error
2. Create fix document: `completed/[timestamp]-fix-installation-[issue].md`
3. Test installation in clean environment
4. Identify missing dependency or incorrect config
5. Update `setup.py` or `pyproject.toml`
6. Update installation documentation
7. Test in multiple environments (if possible)
8. Verify & commit

### Scenario 3: Documentation Example Doesn't Work

**Workflow**:
1. Capture which example and what error
2. Create fix document: `completed/[timestamp]-fix-doc-example-[location].md`
3. Complete **documentation** pre-flight checklist
4. Test example in clean environment
5. Verify API signatures in source code
6. Fix example (update imports, parameters, data)
7. Add copy-paste test to prevent regression
8. Verify & commit

### Scenario 4: Missing Feature or Enhancement

**Workflow**:
1. Assess if single cohesive change or needs 3+ stories
2. If single fix: Create `completed/[timestamp]-add-[feature].md`
3. Complete **code** pre-flight checklist
4. Write tests for new feature (TDD)
5. Implement feature
6. Add documentation
7. Verify & commit
8. Request QA review and merge
9. If needs 3+ stories: Escalate to PM agent for epic creation

---

## Escalation Criteria

**Escalate to full feature planning when the fix requires 3+ coordinated stories**.

**Use sprint fix workflow for**:
- ✅ Single cohesive fix (even if substantial)
- ✅ One logical change that can be implemented and tested as a unit
- ✅ Updates that don't require breaking into multiple independent stories
- ✅ Fixes of any complexity as long as they're a single fix

**Escalate to epic/PRD when**:
- ❌ Requires 3+ separate stories to implement
- ❌ Multiple independent changes that should be tracked separately
- ❌ Changes that need phased rollout across stories
- ❌ Work that needs to be distributed across multiple development cycles

**Examples**:
- ✅ **Sprint Fix**: Adding complete adjustments database (even if large) - single cohesive feature
- ✅ **Sprint Fix**: Rewriting data ingestion logic (even if complex) - one logical change
- ❌ **Escalate**: "Add user authentication" - needs multiple stories (login UI, backend auth, session management, etc.)
- ❌ **Escalate**: "Implement portfolio analytics" - needs multiple stories (metrics engine, visualization, export, etc.)

**Escalation Path**:
1. Document issue in `docs/internal/KNOWN_ISSUES.md`
2. Create epic using `/pm` agent: `*create-brownfield-epic`
3. Follow full brownfield PRD process
4. Return to this workflow for individual story implementations

---

## AI Agent Guidelines

**If you are an AI agent (like Claude Code) handling user-reported issues**:

### Do's:
✅ **ALWAYS create a fix branch first** (MANDATORY - see Step 1)
✅ Always complete the mandatory pre-flight checklist
✅ Document every step in timestamped fix file
✅ Test all code examples before committing
✅ Verify API signatures against source code
✅ Use real implementations (no mocks)
✅ Follow TDD: tests before implementation
✅ **Request QA review before merging** (see QA-REVIEW-GUIDE.md)
✅ **Merge to main only after QA approval**
✅ **Delete branch after successful merge**
✅ Ask user for clarification if needed
✅ Escalate if issue is larger than expected

### Don'ts:
❌ **Work directly on main branch** (ALWAYS use fix branch)
❌ **Merge without QA approval** (ALWAYS get review first)
❌ Skip pre-flight checklist "for efficiency"
❌ Guess at API signatures without verification
❌ Use "foo"/"bar" in examples
❌ Commit without running verification checklist
❌ Mix unrelated fixes in one commit
❌ Skip documentation updates
❌ Use mocking frameworks (violates CR-002)
❌ **Leave fix branches unmerged or undeleted**

### Handling Ambiguity:
- If fix scope is unclear: Ask user
- If API behavior is unclear: Read source code
- If test approach is unclear: Reference existing tests
- If severity is unclear: Err on side of higher severity

### Efficiency Tips:
- Run multiple verification commands in parallel when possible
- Use grep to find all occurrences of issue
- Reference existing fix documents for format
- Copy pre-flight checklist from `active-session.md`

---

## References

- **QA Review Guide**: `QA-REVIEW-GUIDE.md` (in this directory) - How to review fixes
- **Main Sprint Debug Guide**: `README.md` (in this directory)
- **Active Session Template**: `fixes/active-session.md`
- **Fix History**: `fixes/fix-history.md`
- **Coding Standards**: `docs/internal/architecture/coding-standards.md`
- **Zero-Mock Enforcement**: `docs/internal/architecture/zero-mock-enforcement.md`
- **Documentation Standards**: `docs/internal/architecture/DOCUMENTATION_QUALITY_STANDARDS.md`
- **Known Issues**: `docs/internal/KNOWN_ISSUES.md`
- **Project Constitution**: `docs/internal/architecture/constitution.md`

---

## Metrics to Track (Optional)

If tracking metrics over time, add to `fixes/summary-statistics.md`:

- Total external user issues reported: X
- Critical issues: Y
- Average fix time: Z hours
- Documentation fixes vs code fixes ratio
- Most common issue patterns
- User impact (users affected per issue)

---

**Questions or Issues with This Workflow?**

Contact project maintainer or open issue in `docs/internal/KNOWN_ISSUES.md`.

---

**Version History**:
- 2025-10-24: Initial version created based on existing sprint-debug workflow
- 2025-10-24: Added mandatory branching workflow and QA review process
- 2025-10-24: Updated escalation criteria - focus on "3+ stories" not time/complexity; removed time constraints
