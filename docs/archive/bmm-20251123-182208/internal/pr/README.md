# Pull Request Documentation

This directory contains detailed documentation for significant pull requests, particularly those involving major changes, refactoring, or test implementations.

## Naming Convention

Documents follow this naming pattern:

```
YYYY-MM-DD-PR{number}-{commit}-{description}.md
```

**Example:**
```
2025-10-13-PR1-335f312-test-suite-implementation.md
```

Where:
- `YYYY-MM-DD`: Date the document was created
- `PR{number}`: Pull request number (e.g., PR1, PR42)
- `{commit}`: Short commit hash (7 characters) at time of documentation
- `{description}`: Brief kebab-case description of the content

## Purpose

These documents serve as:

1. **Historical Record**: Detailed snapshots of major changes and their rationale
2. **Decision Log**: Documentation of architectural decisions and trade-offs
3. **Review Artifacts**: Comprehensive analysis for code review and future reference
4. **Knowledge Transfer**: Context for future developers understanding the codebase evolution

## Document Types

Common document types include:

- **Test Suite Implementations**: Comprehensive testing documentation (like PR1)
- **Architecture Changes**: Major refactoring or architectural decisions
- **Performance Optimizations**: Benchmark results and optimization strategies
- **API Changes**: Breaking changes and migration guides
- **Security Audits**: Security review findings and remediation

## Maintenance

- Documents are **immutable** once merged - they represent historical truth
- For updates or corrections, create a new document with updated date/commit
- Reference the original document and explain what changed

## Index

### 2025

- **2025-10-13-PR1-335f312-test-suite-implementation.md**
  - Comprehensive test suite for rustybt.lib Cython modules
  - 112 tests covering 2,028 lines of code
  - Documents issues found and fixes implemented

- **2025-10-13-CI-BLOCKING-dependency-issues.md** 🟡 **IN PROGRESS**
  - Critical investigation: All CI/CD workflows failing
  - ✅ Fixed: Numpy/numexpr version conflicts (Python 3.12/3.13)
  - ✅ Fixed: Python version classifiers mismatch
  - ❌ Blocking: Editable install module import failures
  - Related commits: f5bc8f8, 9789fdf, d9b219d, a3ac611, 798441d

---

*Last Updated: October 13, 2025*
