# Senior Developer Review - Validation Checklist

## Context Loading
- [ ] Story file loaded from `{{story_path}}`
- [ ] Story Status verified as one of: review, ready-for-review
- [ ] Epic and Story IDs resolved ({{epic_num}}.{{story_num}})
- [ ] Story Context located or warning recorded
- [ ] Epic Tech Spec located or warning recorded
- [ ] Architecture/standards docs loaded (as available)
- [ ] Tech stack detected and documented

## Acceptance Criteria & Task Validation
- [ ] Acceptance Criteria cross-checked against implementation
- [ ] Each AC has evidence (file:line) documenting implementation
- [ ] All tasks marked complete have been verified with evidence
- [ ] No tasks falsely marked as complete
- [ ] File List reviewed and validated for completeness

## Zero-Mock Enforcement
- [ ] Scanned for hardcoded return values (return 10, return True, etc.)
- [ ] Scanned for always-succeeding validations (def validate_*: return True)
- [ ] Scanned for mock/fake/stub/dummy patterns in production code
- [ ] Scanned for empty error handlers (except: pass)
- [ ] Scanned for simplified implementations without proper warning blocks
- [ ] Scanned for TODO/FIXME/HACK comments without issue references
- [ ] Test quality verified (real assertions, not hardcoded expectations)
- [ ] Zero-mock checklist included in review output
- [ ] ZERO-MOCK STATUS determined: PASS (0 HIGH violations) or FAIL

## Orphaned Files Enforcement
- [ ] Scanned for new files created in project root directory
- [ ] Scanned for files placed in wrong directories (outside project structure)
- [ ] Verified new file naming conventions match project standards
- [ ] Verified new files are imported/referenced (not orphaned)
- [ ] Orphaned files checklist included in review output
- [ ] ORPHAN STATUS determined: PASS (0 HIGH violations) or FAIL

## Code Quality & Security
- [ ] Tests identified and mapped to ACs; gaps noted
- [ ] Code quality review performed on changed files
- [ ] Security review performed on changed files and dependencies
- [ ] MCP doc search performed (or web fallback) and references captured

## Review Completion
- [ ] Outcome decided (Approve/Changes Requested/Blocked)
- [ ] Review outcome correctly reflects enforcement results:
  - BLOCKED if any: AC missing, task falsely complete, zero-mock FAIL, orphan FAIL (HIGH)
  - CHANGES REQUESTED if any: MEDIUM severity issues
  - APPROVE if: all validations pass, zero-mock PASS, orphan PASS
- [ ] Review notes appended under "Senior Developer Review (AI)"
- [ ] Change Log updated with review entry
- [ ] Status updated according to settings (if enabled)
- [ ] Story saved successfully

_Reviewer: {{user_name}} on {{date}}_
