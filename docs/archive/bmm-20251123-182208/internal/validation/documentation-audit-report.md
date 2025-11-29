# Documentation Audit Report - CLI Command References

**Date:** 2025-10-13
**Story:** X2.7 - P2 Production Validation & Documentation
**Task:** Task 8-9 - Documentation Audit

## Executive Summary

**Total CLI References Found:** 457 references across all documentation

**Files Audited:**
- ✅ docs/guides/deployment-guide.md (34 CLI references)
- ✅ docs/security-audit.md (1 reference - pytest, not rustybt CLI)
- ✅ README.md (2 references)
- ✅ docs/guides/* (multiple files)
- ✅ Other documentation files

**Critical Issues Found:** 1 major error
**Status:** ❌ FAIL - Documentation contains incorrect command reference

---

## Discrepancies Found

### CRITICAL: Incorrect Command in deployment-guide.md

**File:** `docs/guides/deployment-guide.md`
**Line:** 955
**Severity:** CRITICAL - Command will not work

**Current (INCORRECT):**
```bash
python -m rustybt fetch-data --source yfinance --symbols AAPL,MSFT --start 2024-01-01
```

**Issues:**
1. ❌ **Wrong command name:** `fetch-data` does not exist
2. ❌ **Wrong option name:** `--symbols` (plural) is not valid
3. ❌ **Non-existent option:** `--start` is not supported by test-data

**Correct Command:**
```bash
python -m rustybt test-data --source yfinance --symbol AAPL
```

**Note:** The `test-data` command only supports testing one symbol at a time and does not have date range options. If the documentation intends to describe data ingestion for backtesting, a different command may be needed (e.g., `ingest` or `bundle` commands).

**Fix Required:**
Replace with either:
1. **Option A (Quick fix):** Use correct test-data syntax
   ```bash
   # Test data fetch from yfinance
   python -m rustybt test-data --source yfinance --symbol AAPL
   python -m rustybt test-data --source yfinance --symbol MSFT
   ```

2. **Option B (Full feature):** Use actual data ingestion command if available
   ```bash
   # Ingest data for backtesting
   python -m rustybt ingest --source yfinance --symbols AAPL,MSFT --start 2024-01-01
   ```
   (Requires verification that `ingest` command supports these options)

---

## Verification Results by File

### 1. docs/guides/deployment-guide.md

**Total References:** 34

**Commands Verified:**

| Command | Line | Status | Notes |
|---------|------|--------|-------|
| keygen | 199, 365 | ✅ Pass | Command exists, help verified |
| test-broker | 348, 943 | ✅ Pass | Command exists, options verified |
| test-data | 351 | ✅ Pass | Correct usage |
| fetch-data | 955 | ❌ FAIL | **Command does not exist** |
| verify-config | 354 | ✅ Pass | Command exists |
| encrypt-credentials | 375 | ✅ Pass | Command exists |
| generate-api-token | 457 | ✅ Pass | Command exists |
| paper-trade | 964 | ✅ Pass | Command exists |

**Required Fix:**
- Line 955: Change `fetch-data` to `test-data` and fix options

---

### 2. README.md

**Total References:** 2

**Commands Verified:**

| Command | Line | Status | Notes |
|---------|------|--------|-------|
| rustybt run | 111 | ✅ Pass | Command exists with all options (-f, --start, --end) |
| pytest (not rustybt) | 164 | N/A | Not a rustybt command |

**No fixes required.**

---

### 3. docs/security-audit.md

**Total References:** 1

**Commands Verified:**

| Command | Line | Status | Notes |
|---------|------|--------|-------|
| pytest --cov=rustybt | 219 | N/A | Not a rustybt CLI command, pytest option |

**No fixes required.** (No rustybt CLI commands found)

---

### 4. Other Documentation Files

**Files with CLI references:**
- docs/cli-commands-inventory.md: Documentation created by this validation (all correct)
- docs/data-provider-validation-report.md: Validation report (all correct)
- docs/broker-validation-findings.md: Validation report (all correct)
- docs/architecture.md: 1 reference to `keygen` (correct)
- docs/development/ci-cd-pipeline.md: No rustybt CLI commands
- docs/development/rust-setup.md: Code examples, not CLI usage

**Status:** All other files appear correct based on grep analysis.

---

## Command Verification Matrix

All CLI commands mentioned in documentation verified against actual CLI:

| Command | Exists | Verified Options | Documentation Status |
|---------|--------|------------------|---------------------|
| test-broker | ✅ Yes | --broker, --testnet | ✅ Correct |
| test-data | ✅ Yes | --source, --symbol | ✅ Mostly correct (1 error in deployment-guide) |
| fetch-data | ❌ No | N/A | ❌ DOES NOT EXIST |
| benchmark | ✅ Yes | --output | ✅ Correct |
| paper-trade | ✅ Yes | --strategy, --broker, --duration, --log-file | ✅ Correct |
| analyze-uptime | ✅ Yes | --log-file, --log-dir, --days | ✅ Correct |
| verify-config | ✅ Yes | --env-file | ✅ Correct |
| test-alerts | ✅ Yes | --email, --slack | ✅ Correct |
| run | ✅ Yes | -f, --start, --end | ✅ Correct |
| keygen | ✅ Yes | (no options) | ✅ Correct |
| encrypt-credentials | ✅ Yes | (no options shown in help) | ✅ Correct |
| generate-api-token | ✅ Yes | (no options shown in help) | ✅ Correct |

---

## Test Execution Results

### Commands Tested

**1. test-data (yfinance):**
```bash
$ python3 -m rustybt test-data --source yfinance --symbol SPY
✅ SUCCESS
```

**2. keygen:**
```bash
$ python3 -m rustybt keygen --help
✅ Command exists and displays help
```

**3. encrypt-credentials:**
```bash
$ python3 -m rustybt encrypt-credentials --help
✅ Command exists and displays help
```

**4. generate-api-token:**
```bash
$ python3 -m rustybt generate-api-token --help
✅ Command exists and displays help
```

**5. fetch-data:**
```bash
$ python3 -m rustybt fetch-data --help
❌ FAILURE: No such command 'fetch-data'
```

**6. run:**
```bash
$ python3 -m rustybt run --help
✅ Command exists with options: -f, --start, --end
```

---

## Recommendations

### Immediate Actions (REQUIRED)

**1. Fix deployment-guide.md Line 955** (CRITICAL)
   - Change `fetch-data` to `test-data`
   - Change `--symbols` to `--symbol`
   - Remove `--start` option or use appropriate command for data ingestion

**Priority:** HIGH - Prevents users from running non-existent command

---

### Additional Recommendations (OPTIONAL)

**2. Consider Adding Data Ingestion Command**
   - If bulk data ingestion is a common use case, consider:
     - Documenting the `ingest` or `bundle` commands more prominently
     - Adding options to `test-data` for bulk testing (--symbols, --start, --end)
     - Creating a new command specifically for data validation with date ranges

**3. Documentation Structure**
   - Consider adding a CLI command reference section to main docs
   - Link to cli-commands-inventory.md from deployment-guide
   - Add "See Also" sections with links to related commands

**4. Automated Documentation Testing**
   - Add CI job to extract and test all CLI command examples from docs
   - Prevents future documentation drift from implementation

---

## Acceptance Criteria Compliance

### AC 6: Documentation Audit: CLI Command References

| Requirement | Status | Notes |
|-------------|--------|-------|
| Extract all CLI command references | ✅ Pass | 457 references extracted to command-references.txt |
| Count total references | ✅ Pass | 457 references |
| Audit all documentation files | ✅ Pass | All required files audited |
| Verify command names match CLI | ❌ Fail | 1 command name incorrect (fetch-data) |
| Verify command options/flags correct | ❌ Fail | 2 option errors in deployment-guide.md |
| Execute example commands | ⚠️ Partial | Key commands tested, 1 failure found |
| Document discrepancies | ✅ Pass | This report |

**Overall Status:** ⚠️ PARTIAL - Discrepancies found and documented, fixes required

---

## Files Requiring Updates

### Priority 1: Must Fix
1. **docs/guides/deployment-guide.md**
   - Line 955: Fix fetch-data command
   - Estimated effort: 5 minutes

### Priority 2: Documentation Enhancements (Optional)
1. **README.md** - Add link to CLI command reference
2. **docs/guides/deployment-guide.md** - Add "See Also" links to CLI docs

---

## Summary Statistics

- **Total files audited:** 8+ files
- **Total CLI references:** 457
- **Unique rustybt commands found:** 12
- **Commands verified:** 12
- **Commands with errors:** 1 (fetch-data)
- **Options with errors:** 2 (--symbols, --start in fetch-data context)
- **Critical issues:** 1
- **Minor issues:** 0
- **Files requiring fixes:** 1

---

## Next Steps

1. ✅ Documentation audit complete - report created
2. ⏭️ **Task 10: Apply documentation fixes**
   - Fix deployment-guide.md line 955
   - Verify fix works with actual command execution
   - Commit changes with clear description
3. ⏭️ **Task 11: Update production workflow docs**
   - Update production-checklist.md (if exists)
   - Update troubleshooting.md (if exists)
4. ⏭️ **Task 12: Create comprehensive validation report**

---

**Report Generated By:** Dev Agent (James)
**Report Status:** Complete - 1 critical issue identified
**Action Required:** Fix deployment-guide.md line 955 before production deployment
