*In compliance with the [APACHE-2.0](https://opensource.org/licenses/Apache-2.0) license: I declare that this version of the program contains my modifications, which can be seen through the usual "git" mechanism.*

## [Unreleased]

### Fixed - CI/CD Build System and Package Discovery (2025-10-13)
- **Critical Fix**: Resolved CI smoke test failures where Cython extensions failed to import after installation
  - Root cause: Package discovery not explicitly including all `rustybt*` subpackages
  - Added explicit `include=['rustybt*']` in both `pyproject.toml` and `setup.py`
  - Enhanced `MANIFEST.in` to include all Cython source files (`.pyx`, `.pxd`, `.pxi`)
  - Added compiled extension inclusion (`*.so`, `*.pyd`) in package data
- **Build System Modernization**:
  - Upgraded to `setuptools>=64.0.0` for better PEP 517/660 support
  - Upgraded to `setuptools_scm>=8.0` for improved pyproject.toml integration
  - Cleaned up build-system requirements, removed unused commented lines
  - Preserved backwards compatibility with existing build process
- **CI Improvements**:
  - Added comprehensive package verification step in smoke test workflow
  - Verification checks installed package structure, compiled extensions, and critical imports
  - Improved diagnostic output for debugging installation issues
- **Documentation**:
  - Created comprehensive CI/CD blocking issues analysis (`docs/pr/2025-10-13-CI-BLOCKING-dependency-issues.md`)
  - Created solutions proposal document (`docs/pr/2025-10-13-CI-BLOCKING-solutions-proposal.md`)
  - Documented all attempted solutions and implementation decisions
- **Dependency Management**: Earlier fixes (already applied)
  - Fixed numpy/numexpr version conflicts for Python 3.12/3.13
  - Corrected Python version classifiers to match `requires-python='>=3.12'`
  - Version-specific numexpr constraints aligned with numpy versions

### Fixed - Missing Cython Source Files and Test Coverage
- **Critical Fix**: Added 9 missing Cython source files in `rustybt/lib/` that were previously untracked
  - `adjustment.pyx`, `adjustment.pxd` (1,054 lines) - Corporate action adjustments
  - `_factorize.pyx` (246 lines) - Categorical data factorization
  - `_windowtemplate.pxi` (161 lines) - Rolling window template
  - `_float64window.pyx`, `_int64window.pyx`, `_uint8window.pyx`, `_labelwindow.pyx` - Type-specific windows
  - `rank.pyx` (172 lines) - Ranking algorithms
- **Test Coverage**: Added comprehensive test suite with 112 test cases (103 passing, 9 intentionally skipped)
  - `tests/lib/test_adjustment.py` - 46 tests for all adjustment types
  - `tests/lib/test_factorize.py` - 36 tests for factorization algorithms
  - `tests/lib/test_windows.py` - 30 tests for rolling windows
  - Property-based tests using Hypothesis for mathematical correctness
  - Edge case coverage (empty arrays, large datasets, Unicode, boundary conditions)
  - Performance validation (100K element arrays)
- **Build System**: Updated `.gitignore` to allow `rustybt/lib/` directory (exception to global `lib/` ignore)
- **Documentation**: Added `tests/lib/TEST_SUITE_SUMMARY.md` documenting test implementation and review findings

### Changed
- `.gitignore`: Added exception for `rustybt/lib/` to allow Cython source files while keeping virtual environment `lib/` ignored

### Added - Epic 8: Unified Data Architecture (Story 8.5)
- **DataPortal Integration**: Updated `PolarsDataPortal` to accept `data_source` parameter for unified data access
- **Smart Caching**: Automatic cache wrapping with `use_cache=True` parameter
- **Cache Statistics**: Added `cache_hit_rate` property to track caching performance
- **Architecture Documentation**: Comprehensive unified data management architecture docs (`docs/architecture/unified-data-management.md`)
- **User Guides**: Data ingestion guide, migration guide, caching guide
- **Example Scripts**: `ingest_yfinance.py`, `ingest_ccxt.py`, `backtest_with_cache.py`
- **Deprecation Timeline**: Clear migration path documented (`docs/deprecation-timeline.md`)
- **Integration Tests**: Full test coverage for DataPortal with unified DataSource

### Changed
- `PolarsDataPortal`: Now supports both legacy (`daily_reader`, `minute_reader`) and unified (`data_source`) initialization
- `get_spot_value()` and `get_history_window()`: Now async methods supporting DataSource API
- Documentation structure: Added `docs/guides/` and `docs/api/` directories

### Deprecated
- `PolarsDataPortal(daily_reader=..., minute_reader=...)`: Use `PolarsDataPortal(data_source=...)` instead
- Removal planned for v2.0 (Q2 2026)

### Performance
- Cache hit latency: <10ms (P95)
- Cache read latency: <100ms (P95)
- 10-20x speedup for repeated backtests with caching enabled

### Migration
- Backwards compatible: Old APIs work with deprecation warnings
- Migration script: `scripts/migrate_catalog_to_unified.py`
- See `docs/guides/migrating-to-unified-data.md` for full migration guide

---

2022-11
Contributor(s):
Stefan Jansen
>RELEASE: v2.3 (#146)- moving to PEP517/8
- from versioneer to setuptools_scm
- package_data to pyproject.toml
- tox.ini to pyproject.toml
- flake8 config to .flake8
-removing obsolete setup.cfg
- update all actions
- talib installs from script
- remove TA-Lib constraint and change quick tests to 3.10
- add windows wheels and streamline workflow
- add GHA retry step
- skip two tests that randomly fail on CI
- skip macos Cpy37 arm64
>add win compiler path
>np deps by py version
>add c compiler
>retry
>update talib conda to 4.25
>add c++ compiler
>tox.ini to pyproject.toml
>removing ubuntu deps again
>set prefix in build; move reqs to host
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2022-05
Contributor(s):
Eric Lemesre
>Fixe wrong link (#102)
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2022-04
Contributor(s):
MBounouar
>MAINT: refactoring lazyval + silence a few warnings (#90)* replace distutils.version with packaging.version

* moved the caching lazyval inside zipline

* silence numpy divide errors

* weak_lru_cache small changes

* silence a few pandas futurewarnings

* fix typo

* fix import
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2022-01
Contributor(s):
Norman Shi
>Fix link to the examples directory. (#71)
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2021-11
Contributor(s):
Stefan Jansen
>update conda build workflows
>update docs
>add conda dependency build workflows
>shorten headings
>Add conda dependency build workflows (#70)Adds GH actions to build and upload conda packages for TA-Lib and exchange_calendars.
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2021-10
Contributor(s):
MBounouar
>MAINT: Update development guidelines (#63)* removed unused sequentialpool

* MAINT:Update dev guide (#10)

* fixed links

* fixed a link and deleted a few lines

* fix

* fix

* fix

* Update development-guidelines.rst
>ENH: Add support for exchange-calendars and pandas > 1.2.5 (#57)* first step
* Switched to exchange_calendars
* fix pandas import  and NaT
* include note in calendar_utils
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2021-05
Contributor(s):
Stefan Jansen
>fix src layout
>PACKAGING adopt src layout
>TESTS adapt to src layout
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2021-04
Contributor(s):
Stefan Jansen
>readme formatting
>multiple cleanups
>editing headlines
>DOCS edits
>retry
>DOCS refs cleanup
>conda packaging and upload workflows
>DOCS review
>ta-lib conda recipe
>docs revision
>manifest update - include tests
>windows wheel talib test
>workflow update - rebuild cython
>conda workflow cleanup
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2021-03
Contributor(s):
Stefan Jansen
>docs update
>update from master
- - - - - - - - - - - - - - - - - - - - - - - - - - -


2021-02
Contributor(s):
Stefan Jansen
>fixed adjustment test tz info issues
- - - - - - - - - - - - - - - - - - - - - - - - - - -
