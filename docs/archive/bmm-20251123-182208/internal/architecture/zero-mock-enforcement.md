# Zero-Mock Enforcement Guidelines

## Developer Commandments

### The Five Absolutes
1. **NEVER** return hardcoded values in production code
2. **NEVER** write validation that always succeeds
3. **NEVER** simulate when you should calculate
4. **NEVER** stub when you should implement
5. **NEVER** claim completion for incomplete work
6. 5. **NEVER** simplify a test to avoid an error

## Pre-Commit Checklist

Before EVERY commit, verify:

- [ ] No TODO/FIXME/HACK comments without issue tracking
- [ ] No hardcoded return values (search for: `return 10`, `return 1.0`, `return True`)
- [ ] No empty except blocks or pass statements in production code
- [ ] No "mock", "fake", "stub", "dummy" in variable/function names
- [ ] No simplified implementations without SIMPLIFIED warning blocks
- [ ] All tests exercise real functionality, not mocks
- [ ] All validations perform actual checks

## Code Review Requirements

### Mandatory Review Points

1. **Return Statements**
   - ❌ BAD: `return 10  # Will implement later`
   - ✅ GOOD: `return self.calculate_actual_return(data)`

2. **Validation Functions**
   - ❌ BAD: `def validate_data(data): return True`
   - ✅ GOOD: `def validate_data(data): return all([check_ohlc(d) for d in data])`

3. **Error Handling**
   - ❌ BAD: `try: ... except: pass`
   - ✅ GOOD: `try: ... except ValueError as e: raise ValidationError(f"Data validation failed: {e}")`

4. **Test Assertions**
   - ❌ BAD: `assert result == 10  # Mock value`
   - ✅ GOOD: `assert result == strategy.calculate_expected_return(test_data)`

## QA Verification Process

### Story Completion Criteria

No story can be marked complete without:

1. **Mock Scan Results**
   ```bash
   python scripts/detect_mocks.py
   # Must return: "0 mock patterns found"
   ```

2. **Validation Test**
   ```bash
   python scripts/test_with_invalid_data.py
   # Must catch all intentional errors
   ```

3. **Unique Results Test**
   ```bash
   python scripts/verify_unique_results.py
   # Must show different results for different inputs
   ```

4. **Performance Validation**
   ```bash
   python scripts/benchmark_real_execution.py
   # Must show actual computation time, not instant returns
   ```

### Epic Completion Gate

Epic 5 is NOT complete until:

- [ ] Mock detection finds ZERO issues across entire codebase
- [ ] All 7 stories (5.0-5.6) marked complete with verification
- [ ] Independent code audit confirms no mocks
- [ ] Performance benchmarks validated by external party
- [ ] Legal review of all performance claims
- [ ] Production readiness checklist 100% complete

## Automated Enforcement

### CI/CD Pipeline Checks

```yaml
# .github/workflows/no-mock-enforcement.yml
name: Zero-Mock Enforcement
on: [push, pull_request]

jobs:
  mock-detection:
    runs-on: ubuntu-latest
    steps:
      - name: Scan for mock patterns
        run: |
          python scripts/detect_mocks.py --strict
          if [ $? -ne 0 ]; then
            echo "::error::Mock patterns detected! Fix before merging."
            exit 1
          fi

      - name: Validate no hardcoded returns
        run: |
          python scripts/detect_hardcoded_values.py

      - name: Check validation functions
        run: |
          python scripts/verify_validations.py

      - name: Test result uniqueness
        run: |
          python scripts/test_unique_results.py
```

### Pre-Commit Hook

```python
#!/usr/bin/env python
# .git/hooks/pre-commit

import subprocess
import sys

def check_for_mocks():
    """Prevent commits containing mock code."""
    result = subprocess.run(['python', 'scripts/detect_mocks.py', '--quick'],
                          capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ COMMIT BLOCKED: Mock code detected!")
        print(result.stdout)
        print("\nTo override (NOT RECOMMENDED):")
        print("  git commit --no-verify")
        return False
    return True

if __name__ == "__main__":
    if not check_for_mocks():
        sys.exit(1)
```

## Reporting Requirements

### Weekly Mock Status Report

Every Friday, generate:

1. **Mock Inventory Update**
   - Total mocks remaining
   - Mocks removed this week
   - New mocks added (should be 0)

2. **Story Progress**
   - Stories completed with verification
   - Blockers identified
   - Timeline adjustments needed

3. **Risk Assessment**
   - Technical risks discovered
   - Performance impacts measured
   - User impact assessment

## Escalation Process

### When Mock Code is Found

1. **Immediate Actions**
   - Block the PR/commit
   - Create priority issue
   - Notify tech lead

2. **Documentation Required**
   - Why was mock code written?
   - What is blocking real implementation?
   - Estimated time to fix

3. **Temporary Exception Process** (RARE)
   - Must have VP Engineering approval
   - Must include:
     ```python
     # TEMPORARY MOCK - APPROVED BY: [Name] DATE: [Date] ISSUE: #XXX
     # EXPIRES: [Date - max 7 days]
     # REASON: [Specific blocker]
     # WARNING: NOT FOR PRODUCTION USE
     ```

## Success Metrics Dashboard

### Real-Time Monitoring

```
┌─────────────────────────────────────┐
│      ZERO-MOCK ENFORCEMENT          │
├─────────────────────────────────────┤
│ Current Mock Count:         0       │
│ Days Since Last Mock:      3        │
│ Stories Verified Complete:  2/7      │
│ Code Coverage (Real):       67%      │
│ Mock Detection Runs Today:  14       │
│ Build Status:              ✅        │
└─────────────────────────────────────┘
```

## Developer Pledge

```
I, [Developer Name], pledge to:
- Write only real implementations
- Never hide incomplete work with mocks
- Test with actual functionality
- Document any simplifications clearly
- Hold my teammates to the same standard

Signed: _______________
Date: _________________
```

## Consequences

### For Violations

1. **First Offense**: Code review training required
2. **Second Offense**: All code requires senior review
3. **Third Offense**: Removed from Epic 5 development

### For Success

1. **Zero mocks maintained for 30 days**: Team celebration
2. **Epic 5 completed on time**: Bonus consideration
3. **External audit passed**: Public recognition

---

## Remember

**Every mock is technical debt.**
**Every stub is a lie to users.**
**Every placeholder is a broken promise.**

**We build real software that does real things.**
