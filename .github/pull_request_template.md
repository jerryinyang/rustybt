## Description

<!-- Brief description of changes. What problem does this PR solve? -->

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] CI/CD changes

## Related Issues

Closes #<!-- issue number -->
Related to #<!-- issue number -->

## Checklist

### Code Quality
- [ ] Code follows project style guidelines (ruff + black)
- [ ] Type hints added/updated for new code (mypy strict)
- [ ] Code complexity ≤10 (McCabe) for all new functions
- [ ] No code quality CI violations
- [ ] Code has been self-reviewed

### Zero-Mock Compliance
- [ ] No mock/fake/stub implementations in production code
- [ ] No hardcoded return values (e.g., `return 10`, `return 1.0`)
- [ ] All validation functions reject invalid data
- [ ] Different inputs produce different outputs
- [ ] All calculations perform real work (no instant returns)

### Testing
- [ ] Unit tests added/updated for new/changed code
- [ ] Property-based tests added (if applicable)
- [ ] All tests pass locally
- [ ] Coverage ≥90% for core modules, ≥95% for financial modules
- [ ] Integration tests added (if applicable)
- [ ] Edge cases covered in tests

### Security
- [ ] No secrets committed (API keys, passwords, tokens)
- [ ] No High severity bandit issues
- [ ] Input validation added for user-facing code
- [ ] Dependencies reviewed for known vulnerabilities
- [ ] Security best practices followed

### Documentation
- [ ] Code comments added for complex logic
- [ ] Docstrings added/updated (Google style)
- [ ] README updated (if needed)
- [ ] CHANGELOG.md updated with changes
- [ ] Architecture diagrams updated (if applicable)
- [ ] API documentation updated (if applicable)

### Performance
- [ ] Performance impact assessed
- [ ] Benchmarks added for performance-critical code
- [ ] No significant performance regressions

## Test Plan

<!-- Describe how you tested this change -->

### Manual Testing
<!-- Steps to manually verify this change -->

### Automated Testing
<!-- Describe automated tests added -->

## Screenshots (if applicable)

<!-- Add screenshots for UI changes or terminal output -->

## Breaking Changes

<!-- List any breaking changes and migration path -->

## Performance Impact

<!-- Describe any performance improvements or regressions -->

## Additional Notes

<!-- Any additional information reviewers should know -->

---

## Reviewer Checklist

- [ ] Code quality checks pass
- [ ] Zero-mock enforcement passes
- [ ] Security checks pass
- [ ] All tests pass
- [ ] Code review completed
- [ ] Documentation is adequate
- [ ] Performance is acceptable
