# RustyBT Production Readiness Gap Analysis

Date: 2025-10-11

## Executive Summary

Running the production readiness checklist surfaced multiple blockers. The project is NOT ready for production as-is. Primary gaps: failing/blocked test execution and missing markers, mypy strict failures across legacy modules, extensive lint/format violations, and security scan findings (1 High, 11 Medium via bandit; 44 dependency vulnerabilities via safety). CLI tooling and documentation exist but validation (paper trading, benchmark) has not been executed in this environment.

## Scope and Method

- Environment: macOS (Python 3.13 venv), repo current branch `main` with uncommitted changes.
- Commands executed (high level): pytest (with selective ignores due to marker errors), mypy (project config), ruff, black --check, bandit, safety, CLI help checks, docs presence checks.
- Note: Results reflect local environment; CI may vary based on configured extras and runners.

## Findings and Recommended Actions

### 1) Testing & Coverage

Observed:
- pytest aborts early due to undefined markers: `memory` and `api_integration` (strict-markers enabled). Some tests also required extras (`freezegun`, `responses`) before installation.
- Coverage was not produced due to early abort.

Actions:
- Add missing markers to pytest configuration:
  - pyproject.toml → [tool.pytest.ini_options].markers: add `"memory: memory profiling benchmarks"` and `"api_integration: marks tests requiring external API integration"`.
- Ensure test extras are installed consistently:
  - Prefer: `uv sync -E test` (or) `pip install -e ".[test]"`.
- Short term to unblock local runs: skip heavy/integration markers by default when validating unit coverage:
  - `pytest -m "not memory and not api_integration and not live and not ib_integration" --cov=rustybt`.
- Medium term: stabilize integration tests with opt-in marker selection and reliable fixtures.
- Target: restore successful run with overall coverage ≥ 90% per [tool.coverage.report.fail_under].

Acceptance criteria:
- `pytest` passes on developer machine and CI with agreed marker selection.
- Coverage report ≥ 90% across included sources.

### 2) Type Checking (mypy --strict)

Observed:
- `mypy --strict` across the entire tree reports 2000+ errors, largely from legacy Zipline-derived modules and libraries lacking stubs (pandas, exchange_calendars, networkx, etc.).

Actions:
- Align execution with the documented gradual typing strategy already captured in pyproject:
  - Limit strict enforcement in CI to: `rustybt/exceptions.py`, `rustybt/utils/logging.py`, `rustybt/utils/error_handling.py` (and any Epic 8 modules already made strict-clean).
  - Ensure mypy runs with project config (`python3 -m mypy` without manual `--strict` overrides), honoring the `[[tool.mypy.overrides]]` relaxations.
- Add/confirm stubs where feasible (already listed in dev extras): `pandas-stubs`, `types-networkx`, etc.; for `exchange_calendars`, continue `ignore_missing_imports` until stubs exist.
- Fix a few low-hanging annotations that cause top-level errors even under relaxed modules, e.g.:
  - `rustybt/extensions.py`: annotate `extension_args: dict[str, str]` (as appropriate) and `custom_types: dict[str, type]`.

Acceptance criteria:
- mypy passes in CI per scoped modules (0 errors) while legacy areas remain on a tracked migration path.

### 3) Linting & Formatting (ruff, black)

Observed:
- `ruff check` reports a large number of findings (docstrings, import order, annotations, invalid noqa directives).
- `black --check` indicates 173 files would be reformatted.

Actions:
- Run auto-fixes locally, then follow-up on remaining warnings:
  - `ruff check . --fix` (repeat until stable), then `black .`.
- Fix invalid `# noqa` directives by specifying exact codes.
- If desired, narrow docstring enforcement for legacy files via per-file ignores in `[tool.ruff.lint.extend-per-file-ignores]` to prevent noisy non-functional diffs during migration.
- Add/verify pre-commit hooks to keep new diffs clean (`ruff`, `black`, `mypy` on changed files).

Acceptance criteria:
- `ruff check` and `black --check` pass in CI.

### 4) Security (bandit, safety)

Observed (bandit):
- High: `tarfile.extractall` without validation at `rustybt/data/bundles/quandl.py:326`.
- Medium: exec/eval usage (algorithm.py, utils/preprocess.py, utils/run_algo.py), SQL expressions via f-strings, potential request timeout issues flagged.

Observed (safety):
- 44 dependency vulnerabilities across transitive packages (notably `torch`, `streamlit`, `regex`, `tornado`, `django`), likely from dev/jupyter stacks.

Actions:
- High (must-fix): safe tar extraction guard
  - Validate members before extraction to prevent path traversal:
    ```python
    base = Path(output_dir).resolve()
    for m in tar.getmembers():
        dest = (base / m.name).resolve()
        if not str(dest).startswith(str(base)):
            raise ValueError(f"Unsafe tar member: {m.name}")
    tar.extractall(output_dir)
    ```
- Exec/Eval review:
  - `algorithm.py` and `utils/run_algo.py`: restrict inputs to trusted sources, prefer AST validation or whitelisting when possible; replace `eval` with `ast.literal_eval` where semantics allow.
  - Document threat model (user-provided code vs. trusted strategy modules) and enforce guardrails accordingly.
- SQL string construction:
  - Avoid direct f-strings for table/column names unless sanitized/whitelisted; use parameterized queries where supported.
- Requests timeouts:
  - Ensure every `requests.*` call explicitly supplies `timeout=`; if bandit false-positives remain, annotate `# nosec B113` with justification.
- Dependencies:
  - Separate prod vs dev extras; ensure production images/environments do NOT include heavy/jupyter stacks unless required.
  - Pin or upgrade vulnerable packages to patched ranges; where usage is not required in prod, exclude them from the production environment.

Acceptance criteria:
- bandit: 0 High; Medium findings either remediated or justified with documented `# nosec` annotations.
- safety: no High/Critical vulnerabilities in production lock; remaining items tracked with remediation plan and environment scoping.

### 5) Configuration & Secrets

Observed:
- `.env` is listed in `.gitignore` (good). No `.env` file present locally (expected). Permissions check pending once present.

Actions:
- Ensure `.env` (or secrets store) in prod has `chmod 600` semantics.
- Use `python -m rustybt keygen` and `python -m rustybt encrypt-credentials` to manage credential encryption.

Acceptance criteria:
- Secrets never committed; encrypted at rest; least-privilege keys per environment.

### 6) CLI & Operational Validations

Observed:
- CLI shows expected commands present (analyze-uptime, benchmark, paper-trade, live-trade, test-broker, test-data, verify-config, test-alerts).
- Paper trading validation (30 days) and benchmark suite not executed in this run.

Actions:
- Exercise key flows prior to production:
  - `python -m rustybt test-broker --broker <name> [--testnet]`
  - `python -m rustybt test-data --source <provider>`
  - `python -m rustybt benchmark --suite backtest`
  - `python -m rustybt paper-trade --strategy <file.py> --broker <name> --duration 30d`
  - `python -m rustybt analyze-uptime --log-dir <dir> --start-date ... --end-date ...`

Acceptance criteria:
- All operational commands succeed with expected outputs, and paper trading uptime target (≥ 99.9%) is demonstrated over the validation window.

### 7) Documentation Consistency

Observed:
- Deployment, troubleshooting, and security audit documents exist. Minor inconsistency reported previously: use `test-data` (not `fetch-data`).

Actions:
- Update references to reflect the actual command names.
- Keep guides aligned with working CLI and marker configuration.

Acceptance criteria:
- Docs match CLI and default workflows; no dead commands in guides.

## Prioritized Remediation Plan

1. Security Hotfixes (P0)
   - Implement safe tar extraction; review/guard exec/eval usage; parameterize SQL; verify timeouts.
   - Outcome: bandit 0 High; Medium either fixed or justified.

2. Test Unblocking + Coverage (P0)
   - Add `memory` and `api_integration` markers; install test extras; run unit tests excluding heavy markers; target ≥ 90% coverage for core modules.

3. Lint/Format Baseline (P1)
   - Run `ruff --fix` and `black` to establish a clean baseline; adjust per-file ignores for legacy docstrings if needed; enable pre-commit.

4. Type Checking Scope & Migration (P1)
   - Enforce mypy on strict-clean modules per pyproject; create a backlog to migrate additional modules; add stubs/overrides as needed.

5. Dependency Hygiene (P1)
   - Split prod/dev extras; prune unused packages in production; upgrade/pin vulnerable dependencies; add a weekly safety scan in CI.

6. Operational Validations (P2)
   - Execute benchmark and paper trading validation; collect uptime/error KPIs; finalize go-live evidence.

## Ownership & Acceptance Criteria

- Security: Fixes merged, bandit High=0; documented justifications for any acceptable Medium.
- QA/Testing: pytest green (unit suite), coverage ≥ 90% for core; integration tests opt-in and stable.
- DX/Quality: ruff & black pass in CI; pre-commit hooks active.
- Type Safety: mypy clean on scoped modules; migration plan tracked.
- Ops: Broker/data checks pass; benchmark and uptime validated.

## Risks if Unaddressed

- Security exposure via archive extraction or dynamic code execution.
- Poor maintainability and drift without lint/format/type baselines.
- Inability to certify reliability (tests/coverage) before go-live.
- Regulatory/audit gaps if logs/validations aren’t proven pre-deployment.

## Command Reference (quick start)

```bash
# Test & coverage (unit focus)
uv sync -E test
pytest -m "not memory and not api_integration and not live and not ib_integration" \
  --cov=rustybt --cov-report=term

# Type check (scoped by pyproject)
python3 -m mypy

# Lint/format
ruff check . --fix
black .

# Security
bandit -r rustybt -ll -i
safety scan  # (preferred over deprecated `check`)

# Ops checks
python -m rustybt test-broker --broker <name>
python -m rustybt test-data --source <provider>
python -m rustybt benchmark --suite backtest
python -m rustybt paper-trade --strategy <file.py> --broker <name> --duration 30d
python -m rustybt analyze-uptime --log-dir ~/.rustybt/logs --start-date <date> --end-date <date>
```
