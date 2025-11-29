# Epic X3: Standardized Backtest Output Organization

**Version:** 0.1
**Created:** 2025-10-18
**Status:** Draft
**Author:** John (PM)
**Type:** Brownfield Enhancement

---

## Epic Overview

### Epic Goal

Implement a production-grade backtest artifact management system that automatically organizes all outputs (results, code, metadata) in timestamped directories within a central `backtests/` location, enabling reproducibility and historical tracking.

### Background and Motivation

As RustyBT matures and users run more backtests, the current ad-hoc output organization creates several problems:
1. **Scattered outputs**: Files created in execution location make it difficult to track which results came from which strategy version
2. **No code capture**: Exact strategy code that produced results is not saved, hindering reproducibility
3. **Data in unexpected locations**: Jupyter notebooks create local `csvdir_data/` folders instead of using central storage
4. **Difficulty comparing results**: No systematic organization across backtest runs

**Current Observed Behavior:** When running `docs/examples/notebooks/10_full_workflow.ipynb`, outputs are created directly in the notebooks directory:
- `backtest_results.csv` (376KB)
- `backtest_results.parquet` (85KB)
- `summary_statistics.csv` (167 bytes)
- `optimization_results.csv` (652 bytes)
- `csvdir_data/` directory with downloaded data
- `market_data.parquet` (143KB)

This enhancement establishes a production-grade artifact management system that will support future features like automated strategy comparison, performance tracking over time, and integration with CI/CD pipelines.

### Integration Requirements

- Integrate with Epic 3's DataCatalog to link backtests with cached datasets
- Maintain compatibility with existing report generation and analytics systems
- Work seamlessly across CLI and Jupyter notebook execution environments
- Preserve all existing backtest execution APIs without breaking changes

### Impact Assessment

**Impact Level:** Moderate (some existing code changes)

**Affected Components:**
- `rustybt/algorithm.py` - Backtest execution hooks
- `rustybt/data/adapters/` - Path resolution for data downloads
- Report generation systems - Output path redirection
- DataCatalog integration - Backtest linkage

---

## Requirements Summary

### Functional Requirements

- **FR1:** Create central `backtests/` directory for all backtest outputs
- **FR2:** Assign unique millisecond-precision timestamp IDs to each run
- **FR3:** Create dedicated subdirectory `backtests/{backtest_id}/` per run
- **FR4-5:** Save all results, statistics, reports to backtest directory
- **FR6:** Detect and copy non-framework strategy code via import analysis
- **FR7:** Support optional `strategy.yaml` for explicit code capture control
- **FR8:** Import analysis identifies local modules (not framework/stdlib/site-packages)
- **FR9:** Generate `backtest_metadata.json` with full provenance
- **FR10:** Log backtest ID and output path for user reference
- **FR11-12:** Fix data adapters to use central bundle storage (not local folders)

### Non-Functional Requirements

- **NFR1:** Code capture completes in <5 seconds for typical projects
- **NFR2:** Add <2% overhead to backtest execution time
- **NFR3:** Human-readable JSON metadata (pretty-printed)
- **NFR4:** Gracefully handle missing files (warn, don't fail)
- **NFR5:** Thread-safe ID generation for concurrent runs
- **NFR6:** Seamless CLI and Jupyter notebook support

### Compatibility Requirements

- **CR1:** Integrate with DataCatalog `backtest_data_links` table
- **CR2:** Jupyter notebook compatibility (correct path resolution)
- **CR3:** CLI compatibility (no flag changes required)
- **CR4:** Data adapter compatibility (all write to central storage)
- **CR5:** Report generation compatibility (transparent path redirection)

---

## Technical Approach

### New Components

**New Module:** `rustybt/backtest/artifact_manager.py`
- `BacktestArtifactManager` class for output organization
- Directory creation and path resolution
- Output redirection logic

**New Module:** `rustybt/backtest/code_capture.py`
- `StrategyCodeCapture` class for import analysis
- File copying with directory structure preservation
- Optional `strategy.yaml` support

**Extended Module:** `rustybt/algorithm.py`
- Integrate artifact manager hooks in `TradingAlgorithm.run()`
- Expose `backtest.output_dir` attribute

### Configuration

```yaml
backtest_output:
  enabled: true
  base_dir: "backtests"
  code_capture_mode: "import_analysis"  # or "strategy_yaml"
```

### Directory Structure

```
backtests/
└── 20251018_143527_123/           # YYYYMMDD_HHMMSS_mmm
    ├── results/
    │   ├── backtest_results.csv
    │   ├── backtest_results.parquet
    │   ├── summary_statistics.csv
    │   ├── optimization_results.csv
    │   └── reports/
    │       ├── basic_report.html
    │       └── advanced_report.html
    ├── code/
    │   ├── my_strategy.py
    │   └── utils/
    │       └── indicators.py
    └── metadata/
        └── backtest_metadata.json
```

### Metadata Format

```json
{
  "backtest_id": "20251018_143527_123",
  "timestamp": "2025-10-18T14:35:27.123Z",
  "framework_version": "0.5.0",
  "python_version": "3.12.1",
  "strategy_entry_point": "/path/to/my_strategy.py",
  "captured_files": [
    "my_strategy.py",
    "utils/indicators.py"
  ],
  "data_bundle_info": {
    "bundle_name": "quandl",
    "dataset_ids": ["uuid-dataset-1", "uuid-dataset-2"]
  }
}
```

---

## Stories

### Story X3.1: Create Backtest Output Directory Management

**User Story:**
As a **quantitative researcher**,
I want **each backtest run to automatically create a uniquely identified output directory**,
so that **all my backtest results are organized chronologically and never overwrite previous runs**.

**Acceptance Criteria:**
1. System generates unique backtest ID using format `YYYYMMDD_HHMMSS_mmm` (millisecond precision timestamp)
2. Creates directory structure: `backtests/{backtest_id}/` on backtest initialization
3. ID generation is thread-safe for concurrent backtest execution
4. Logs backtest ID and output path to console/notebook at INFO level
5. Validates `backtests/` directory is writable before proceeding
6. Creates subdirectories: `results/`, `code/`, `metadata/`

**Integration Verification:**
- **IV1:** Verify backtests run successfully with new directory creation, producing same results (checksum comparison)
- **IV2:** Confirm `TradingAlgorithm.run()` properly initializes directory structure without breaking existing backtest scripts
- **IV3:** Verify directory creation adds <100ms overhead to backtest startup time

**Implementation Notes:**
- Use `datetime.now()` with microsecond precision, format to milliseconds
- Thread-safe: Use `threading.Lock()` around ID generation
- Path validation: Check write permissions before proceeding

---

### Story X3.2: Redirect Backtest Results to Organized Output Directory

**User Story:**
As a **backtest user**,
I want **all my backtest outputs (CSV, Parquet, reports) to automatically save to the timestamped directory**,
so that **I can find all artifacts from a specific run in one place**.

**Acceptance Criteria:**
1. All result files (CSV, Parquet, JSON) write to `backtests/{backtest_id}/results/`
2. HTML/PDF reports write to `backtests/{backtest_id}/results/reports/`
3. Summary statistics and analytics outputs write to `backtests/{backtest_id}/results/`
4. File paths are resolved correctly in both CLI and Jupyter notebook environments
5. Existing file writing APIs work without modification (transparent path redirection)
6. User can access backtest output directory via `backtest.output_dir` attribute

**Integration Verification:**
- **IV1:** Run full workflow notebook (`10_full_workflow.ipynb`) and verify all expected outputs are created in new location with correct content
- **IV2:** Validate that report generation, CSV export, and Parquet writing all use redirected paths without code changes in user strategies
- **IV3:** Confirm file I/O performance unchanged (benchmark against previous version)

**Implementation Notes:**
- Modify result export methods to use `artifact_manager.get_output_path(filename)`
- Expose `self.output_dir` on `TradingAlgorithm` instance
- Jupyter detection: Check for `IPython.get_ipython()` to adjust paths

---

### Story X3.3: Implement Strategy Code Capture via Import Analysis

**User Story:**
As a **researcher**,
I want **the exact strategy code that produced my results to be automatically saved**,
so that **I can reproduce or audit backtests weeks or months later**.

**Acceptance Criteria:**
1. On backtest start, analyze strategy entry point for all import statements
2. Identify imported modules that are local files (not framework, stdlib, or site-packages)
3. Copy identified strategy files to `backtests/{backtest_id}/code/` preserving directory structure
4. Detect and copy modules imported via `from X import Y` and `import X` patterns
5. Handle relative imports correctly (e.g., `from .utils import helper`)
6. Log list of captured files at DEBUG level
7. Warn (but don't fail) if imported file not found or not accessible

**Integration Verification:**
- **IV1:** Strategy execution unchanged; copied code is stored but not used for execution
- **IV2:** Test with multi-file strategy project; verify all helper modules captured
- **IV3:** Code capture completes in <5 seconds for projects with <50 files

**Implementation Notes:**
- Use `ast` module to parse strategy file and extract import statements
- Resolve module paths using `importlib.util.find_spec()`
- Filter out modules in `sys.stdlib_module_names` and `site-packages`
- Use `shutil.copy2()` to preserve timestamps

---

### Story X3.4: Support Optional strategy.yaml for Explicit Code Capture

**User Story:**
As a **power user with complex strategy projects**,
I want **to explicitly specify which files constitute my strategy**,
so that **I have full control over code capture when import analysis is insufficient**.

**Acceptance Criteria:**
1. If `strategy.yaml` exists in strategy directory, use it instead of import analysis
2. YAML format specifies: `files: [list of file paths relative to strategy root]`
3. System copies all listed files to `backtests/{backtest_id}/code/`
4. Preserve directory structure based on relative paths in YAML
5. Warn if listed file doesn't exist, but proceed with backtest
6. Log "Using strategy.yaml for code capture" at INFO level when present

**Integration Verification:**
- **IV1:** Backtest runs normally with or without `strategy.yaml` present
- **IV2:** YAML-specified files correctly copied; directory structure preserved
- **IV3:** YAML-based capture has comparable performance to import analysis

**Implementation Notes:**
- Use `pyyaml` to parse `strategy.yaml`
- Schema validation: Ensure `files` key exists and is list of strings
- Example `strategy.yaml`:
  ```yaml
  files:
    - my_strategy.py
    - utils/indicators.py
    - config/strategy_config.json
  ```

---

### Story X3.5: Generate Backtest Metadata JSON

**User Story:**
As a **data analyst**,
I want **metadata about each backtest run automatically recorded**,
so that **I can track what version of my strategy and data produced specific results**.

**Acceptance Criteria:**
1. Create `backtests/{backtest_id}/metadata/backtest_metadata.json` at backtest completion
2. JSON contains: backtest_id, timestamp (ISO8601), framework_version, python_version
3. JSON contains: strategy_entry_point (file path), captured_files (list of paths)
4. JSON contains: data_bundle_info (bundle name, dataset IDs from DataCatalog if available)
5. JSON is pretty-printed (indent=2) for human readability
6. Metadata generation failures log error but don't fail backtest

**Integration Verification:**
- **IV1:** Backtest completes successfully; metadata is written as final step
- **IV2:** DataCatalog integration: dataset IDs correctly retrieved and recorded
- **IV3:** Metadata generation adds <1 second to backtest completion time

**Implementation Notes:**
- Use `json.dump()` with `indent=2` for readability
- Framework version: Import from `rustybt.version`
- Python version: `sys.version`
- Wrap metadata writing in try/except to prevent backtest failure

---

### Story X3.6: Fix Data Adapter to Use Central Bundle Storage

**User Story:**
As a **Jupyter notebook user**,
I want **data downloads to go to the central bundle directory instead of creating local folders**,
so that **my workspace stays clean and data is properly cached for reuse**.

**Acceptance Criteria:**
1. Investigate why `csvdir_data/` is created in notebook directory instead of bundle storage
2. Root cause identified: likely CSV adapter or configuration using `os.getcwd()` instead of configured bundle path
3. Fix data adapters (CSV, CCXT, yfinance) to resolve bundle directory from configuration
4. Add configuration validation on startup to ensure bundle directory is accessible
5. Jupyter notebook environment correctly resolves bundle path relative to project root, not notebook location
6. Update data adapter documentation with path resolution behavior

**Integration Verification:**
- **IV1:** Run `10_full_workflow.ipynb`; verify no `csvdir_data/` created in notebook directory; data appears in configured bundle location
- **IV2:** All three adapters (CSV, CCXT, yfinance) tested; all use central storage
- **IV3:** No performance degradation from path resolution changes

**Implementation Notes:**
- Review `rustybt/data/bundles/csvdir.py` for path resolution logic
- Centralize bundle path resolution in config module
- Jupyter detection: Use project root discovery (find `.git` or `pyproject.toml`)
- Add unit tests for path resolution in different environments

---

### Story X3.7: Integrate Backtest Runs with DataCatalog

**User Story:**
As a **system**,
I want **backtest runs linked to their data sources in the DataCatalog**,
so that **I can track data provenance and enable cache reuse across similar backtests**.

**Acceptance Criteria:**
1. After backtest completes, query DataCatalog for datasets used (via cache keys)
2. Insert record into `backtest_data_links` table with backtest_id and dataset_id(s)
3. Record timestamp when data was accessed/cached
4. Handle case where DataCatalog integration unavailable (log warning, continue)
5. Backtest metadata JSON updated with dataset_ids field
6. DataCatalog queries work correctly when multiple datasets used in single backtest

**Integration Verification:**
- **IV1:** DataCatalog functionality unchanged; backtest linkage is additive
- **IV2:** Run backtest with multiple data sources; verify all dataset IDs captured in metadata and database
- **IV3:** Database insert operations add <500ms to backtest completion

**Implementation Notes:**
- Extend existing `backtest_data_links` table schema (no changes needed if already exists)
- Query DataCatalog after backtest completes: `catalog.get_datasets_for_backtest(backtest_id)`
- Use SQLAlchemy ORM for database inserts
- Graceful degradation: If DataCatalog not available, log warning and skip linkage

---

## Success Metrics

### Functional Metrics
- ✅ 100% of backtest runs create timestamped output directories
- ✅ 100% of strategy code files successfully captured (import analysis + YAML)
- ✅ 100% of backtest outputs redirect to organized directories
- ✅ Zero `csvdir_data/` folders created in notebook directories after fix

### Performance Metrics
- ✅ Code capture: <5 seconds for typical projects
- ✅ Total overhead: <2% of backtest execution time
- ✅ Directory creation: <100ms
- ✅ Metadata generation: <1 second

### Compatibility Metrics
- ✅ All existing example notebooks run without modification
- ✅ All CLI commands work without flag changes
- ✅ All integration tests pass

---

## Risk Assessment

### Technical Risks

**Risk:** Import analysis misses dynamically loaded code
- **Likelihood:** Medium
- **Impact:** Medium (incomplete code capture)
- **Mitigation:** Support optional `strategy.yaml` for explicit file listing

**Risk:** Jupyter notebook path detection fragility
- **Likelihood:** Medium
- **Impact:** Low (fallback to current directory)
- **Mitigation:** Use IPython API with fallback, comprehensive testing

**Risk:** Thread safety in concurrent backtest execution
- **Likelihood:** Low
- **Impact:** High (ID collision, data corruption)
- **Mitigation:** Thread-safe ID generation with locks, integration tests for concurrency

### Integration Risks

**Risk:** Breaking existing workflows expecting outputs in current directory
- **Likelihood:** Medium
- **Impact:** High (user disruption)
- **Mitigation:** Thorough testing with all example notebooks and CLI scripts

**Risk:** Data adapter path issues in different environments
- **Likelihood:** Medium
- **Impact:** Medium (data in wrong location)
- **Mitigation:** Centralize path resolution, environment-specific testing

---

## Dependencies and Assumptions

### Dependencies
- Epic 3 (Data Catalog Architecture) - `backtest_data_links` table and DataCatalog API
- Existing report generation systems (`analytics/reports.py`)
- Data adapters (CCXT, yfinance, CSV)

### Assumptions
- Users want complete backtest reproducibility (code + data + results)
- Timestamped millisecond identifiers sufficient for uniqueness
- Import analysis can reliably detect strategy code through static analysis
- Central data bundle storage already exists and functional
- Users accept disk space usage for persistent backtest storage

### Technical Assumptions
- Python's `ast` module sufficient for import analysis
- File system supports millisecond-precision timestamps
- SQLite database accessible for backtest linkage
- Configuration system supports new `backtest_output` section

---

## Testing Strategy

### Unit Tests
- Backtest ID generation (uniqueness, format)
- Directory creation and validation
- Import analysis (various import patterns)
- YAML parsing and validation
- Metadata JSON generation
- Path resolution (CLI vs Jupyter)

### Integration Tests
- Full backtest run with output capture
- Multi-file strategy code capture
- Concurrent backtest execution (thread safety)
- DataCatalog linkage
- All data adapters (CSV, CCXT, yfinance)

### End-to-End Tests
- Run all example notebooks (`01_getting_started.ipynb` through `10_full_workflow.ipynb`)
- Verify outputs in correct locations
- Verify no local data directories created
- Verify metadata accuracy

### Performance Tests
- Benchmark code capture time
- Benchmark total overhead
- Benchmark concurrent execution

---

## Implementation Sequence

**Phase 1 (Week 1):**
- Story X3.1: Directory management
- Story X3.2: Output redirection

**Phase 2 (Week 2):**
- Story X3.3: Import analysis
- Story X3.4: Optional YAML support

**Phase 3 (Week 3):**
- Story X3.5: Metadata generation
- Story X3.7: DataCatalog integration

**Phase 4 (Week 4):**
- Story X3.6: Data adapter fixes
- Integration testing
- Documentation updates

---

## Documentation Updates

### User Guide
- New section: "Backtest Output Organization"
- Examples of accessing backtest results
- Guide to `strategy.yaml` format

### API Documentation
- `BacktestArtifactManager` class
- `StrategyCodeCapture` class
- `TradingAlgorithm.output_dir` attribute

### Architecture Decision Record
- ADR: Backtest artifact organization design
- Rationale for timestamp-based IDs vs UUIDs
- Rationale for file copying vs git integration

---

## Future Enhancements (Out of Scope)

### Post-MVP Features
- CLI commands for backtest management (`list`, `compare`, `delete`)
- Automatic cleanup/archival of old backtests
- Backtest comparison dashboard
- Integration with experiment tracking tools (MLflow, Weights & Biases)
- Git integration for version control
- Database-backed artifact storage (MinIO/S3)
- Content-addressable storage for deduplication

### Potential Roadmap
- **v1.0:** Basic output organization (this epic)
- **v1.1:** CLI management commands
- **v1.2:** Comparison and analytics tools
- **v2.0:** Integration with ML experiment tracking

---

## Change Log

| Date       | Version | Description                                      | Author   |
|------------|---------|--------------------------------------------------|----------|
| 2025-10-18 | 0.1     | Initial epic creation for backtest output org    | John (PM)|

---

**Status:** Draft - Ready for Review and Approval
