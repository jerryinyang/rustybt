# Known Issues

## Documentation Build

### Pydantic V2 Deprecation Warning in mkdocstrings

**Status**: Informational only - No action required

**Issue**: During `mkdocs build`, an INFO-level message appears:

```
INFO - PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated...
```

**Source**: `mkdocstrings-python` v1.18.2 (third-party dependency)

**Impact**: None
- Build completes successfully
- Documentation quality unaffected
- `--strict` mode passes (only blocks on WARNING/ERROR)
- Future deprecation notice (won't break until Pydantic V3)

**Resolution**:
- No action needed from our side
- Will be fixed in future mkdocstrings-python release
- Monitor upstream: https://github.com/mkdocstrings/python

**Workaround** (optional): Filter the message during CI/CD:
```bash
mkdocs build --strict 2>&1 | grep -v "PydanticDeprecatedSince20"
```

**Last Checked**: 2025-10-17
**Dependencies**: mkdocstrings 0.30.1, mkdocstrings-python 1.18.2

---

## Documentation - Code Execution Examples

### Python API Execution Not Documented

**Status**: Identified - Pending Fix

**Issue**: Documentation examples are CLI-first (`rustybt run`) without showing Python API option

**Impact**: High - User confusion and reduced usability
- Users assume CLI is the only way to run strategies
- Pure Python execution (`python my_strategy.py`) is undocumented in user-facing guides
- Conflicts with Python conventions and standard development workflows
- Makes integration with Jupyter notebooks, IDEs, and scripts harder

**Affected Documentation**:
- Quick Start Guide (`docs/getting-started/quickstart.md`) - Only shows `rustybt run` CLI
- Unknown extent across other user guides - **requires comprehensive audit**

**Evidence**:
- `run_algorithm()` function exists in `rustybt/utils/run_algo.py:328`
- Many advanced examples use Python API (`examples/live_trading_simple.py:166`)
- Pattern already exists: `if __name__ == "__main__": run_algorithm(...)`
- User reported: "Doesn't the framework allow for pure python API format?"

**Root Cause**:
- Documentation written with CLI-first approach (likely inherited from Zipline)
- Python API execution pattern not prioritized in user-facing guides
- Advanced examples use it, but beginners are never taught it

**Recommended Fix**:
1. Update Quick Start to show BOTH execution methods
2. Prioritize Python API as primary method (more Pythonic)
3. Show CLI as alternative for quick testing
4. Add to all user guides: "Run directly: `python my_strategy.py`"
5. Create API execution guide in User Guides section

**Workaround**:
Users can study advanced examples to discover `run_algorithm()` usage pattern:
```python
from rustybt import run_algorithm
import pandas as pd

if __name__ == "__main__":
    result = run_algorithm(
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        initialize=initialize,
        handle_data=handle_data,
        capital_base=100000,
        bundle='yfinance-profiling'
    )
```

**Audit Status**:
- ✅ Quick Start confirmed CLI-only
- ✅ **Full documentation audit COMPLETED** (2025-10-17 sprint-debug session)
- ✅ 114 user-facing files audited
- 📊 **Detailed findings**: See `docs/internal/sprint-debug/python-api-execution-audit-2025-10-17.md`

**Audit Summary**:
- **Critical**: 2 files (index.md, quickstart.md) are CLI-only
- **Problem**: 4+ files show strategies without execution instructions
- **Good**: 7 files demonstrate Python API correctly
- **Gap**: 0 files show both CLI and Python API side-by-side

**Priority Fixes Identified**:
1. **CRITICAL**: Update `docs/index.md` - Add Python API example
2. **CRITICAL**: Update `docs/getting-started/quickstart.md` - Add Python API section
3. **HIGH**: Fix `docs/api/order-management/order-types.md` - Add promised "Complete Examples"
4. **HIGH**: Fix `docs/guides/pipeline-api-guide.md` - Add execution section
5. **MEDIUM**: Add cross-references and complete examples to other docs

**Estimated Fix Time**: 9.5 hours total
- Critical fixes: 1.5 hours
- High priority: 2 hours
- Medium priority: 1 hour
- Long-term improvements: 5 hours

**Last Updated**: 2025-10-17
**Reporter**: User feedback
**Audit By**: James (Dev Agent)
**Assigned to**: Next sprint-debug session (prioritized)
