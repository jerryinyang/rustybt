# RustyBT Documentation & Examples Review

This document summarizes observations from a thorough audit, identifies gaps by priority, and proposes concrete, testable actions to align docs/examples with the current codebase.

## 1) Observations

- Breadth: Strong coverage across architecture, guides (ingestion, caching, validation, exception handling), analytics, optimization, live/paper trading, stories, and QA gates.
- Code–Docs alignment: Most examples reflect the actual APIs. Analytics modules (reports, attribution, risk, trade analysis) are implemented and have tests/examples. Unified DataSource registry, Polars validation, optimization algorithms, and live trading engine/brokers are in place.
- Tooling/CLI: Modern CLI flows exist, including run, ingest-unified, and cache management (stats/list/clean).

## 2) Identified Gaps (by priority)

### High Priority (functional correctness)
- README incorrect imports/usage:
  - CCXT import:
    - Incorrect: `from rustybt.live.brokers import CCXTAdapter`
    - Correct: `from rustybt.live.brokers import CCXTBrokerAdapter`
  - “Community: Documentation: Coming soon” is outdated given the comprehensive docs folder.
- Ingestion CLI mismatch in guides:
  - Docs use `rustybt ingest yfinance ...` for unified ingestion; the implemented unified command is `rustybt ingest-unified ...`. Legacy `ingest` is for bundle registry ingestion.
- Async code in guides:
  - Several ingestion snippets use bare `await` at top level. Must wrap in `asyncio.run(main())` or equivalent.
- DataSource API guide references non-existent classes and registration API:
  - Uses `YFinanceDataSource`, `AlpacaDataSource`, `CCXTDataSource`, and `DataSourceRegistry.register(...)`.
  - Actual pattern is dynamic discovery and `DataSourceRegistry.get_source("<name>", **params)` returning adapters like `YFinanceAdapter`, `AlpacaAdapter`, etc. No public `register` method.
- Caching Guide references unimplemented classes:
  - `MemoryCachedDataSource`, `RedisCachedDataSource` not in repo; implemented wrapper is `CachedDataSource`.
- Broken link:
  - Data Validation Guide references `../architecture/data-adapters.md` (file does not exist).

### Medium Priority (consistency/accuracy)
- CCXT “list exchanges”:
  - Docs suggest `rustybt ingest ccxt --list-exchanges`; CLI implements `ingest-unified --list-sources` and `--source-info`. No `--list-exchanges` handler exists.
- Naming consistency:
  - Docs sometimes mix “DataSource” class names vs adapter names. Recommend consistently positioning via `DataSourceRegistry.get_source("<name>")`.
- Frequency flags:
  - Ensure examples consistently use supported values (`1d`, `1h`, `5m`, `1m`) per CLI and adapters.
- Examples index:
  - “Advanced: Coming soon” is stale; many advanced examples exist (optimization, paper/live, latency simulation, slippage/borrow cost, parallel optimization).

### Low Priority (polish/clarity)
- Add mini quick-start in README for unified ingestion (to reduce confusion with legacy `ingest`).
- Enrich README Quick Start with correct live broker import and link to docs index instead of “coming soon”.
- Minor consistency in “Adapter vs DataSource” terminology across guides.

## 3) Recommended Actions

Below are precise updates with acceptance criteria.

### A. README fixes (high)
- Update CCXT import:
  - Replace: `from rustybt.live.brokers import CCXTAdapter`
  - With: `from rustybt.live.brokers import CCXTBrokerAdapter`
- Update unified ingestion example:
  - Replace legacy `rustybt ingest yfinance ...`
  - With: `rustybt ingest-unified yfinance --bundle my-stocks --symbols AAPL,MSFT,GOOGL --start 2023-01-01 --end 2023-12-31 --frequency 1d`
- Replace “Documentation: Coming soon” with a link to `docs/architecture/index.md` (or a docs landing page).
- Acceptance:
  - README examples run without import errors and CLI works as shown.

### B. Data Ingestion Guide (high)
- Wrap all `await` usage with `asyncio.run(...)` patterns:
  - Provide:
    ```python
    import asyncio, pandas as pd
    from rustybt.data.sources import DataSourceRegistry

    async def main():
        source = DataSourceRegistry.get_source("yfinance")
        await source.ingest_to_bundle(...)

    asyncio.run(main())
    ```
- Standardize CLI to `ingest-unified` (include `--bundle`, `--symbols`, `--start`, `--end`, `--frequency`).
- Remove or revise “Supported exchanges: Run `rustybt ingest ccxt --list-exchanges`”:
  - Option 1: Implement `--list-exchanges` in CLI.
  - Option 2: Replace with: `rustybt ingest-unified --source-info ccxt`.
- Acceptance:
  - Code blocks run as-is; CLI commands validated against `rustybt __main__.py`.

### C. DataSource API Reference (high)
- Replace class-based usage with `DataSourceRegistry.get_source("<name>", **params)` in all examples.
- Remove `DataSourceRegistry.register(...)` (unless you implement it); instruct contributors to place adapters under `rustybt.data.adapters` and import in the registry discovery (as today).
- Replace `YFinanceDataSource`, `AlpacaDataSource`, `CCXTDataSource`, `PolygonDataSource`, `CSVDataSource` with “source = DataSourceRegistry.get_source("yfinance" | "alpaca" | "ccxt" | "polygon" | "csv")”.
- Wrap async calls in `asyncio.run(...)`.
- Acceptance:
  - All code snippets reflect actual public API; no non-existent entities referenced.

### D. Caching Guide (high)
- Remove or clearly mark `MemoryCachedDataSource` and `RedisCachedDataSource` as “Planned/Future”.
- Keep examples focused on `CachedDataSource` (which exists).
- Acceptance:
  - No references to unavailable classes; examples import and run.

### E. Data Validation Guide link fix (high)
- Replace `../architecture/data-adapters.md` with an existing doc:
  - Suggest: `../architecture/unified-data-management.md` or `../api/datasource-api.md`.
- Acceptance:
  - Link checker passes for this document.

### F. Optional CLI enhancement (medium)
- Add `--list-exchanges` to `ingest-unified` for CCXT:
  - Implement discovery via `ccxt.exchanges`.
  - Or document a simple Python snippet to print supported exchanges using ccxt, if not adding CLI.
- Acceptance:
  - `rustybt ingest-unified ccxt --list-exchanges` prints exchanges; or docs no longer mention this flag.

### G. Examples index (medium)
- Update “Advanced: Coming soon” to reflect present advanced examples; add bullets for optimization, paper/live trading, latency simulation, slippage/borrow cost, parallel optimization.
- Acceptance:
  - Examples overview reflects current content.

### H. README live imports (low)
- Ensure live examples import only exported broker names:
  - `from rustybt.live.brokers import PaperBroker, CCXTBrokerAdapter`
- Acceptance:
  - Live code samples import/execute without NameError.

## 4) Risk Assessment

- Risk of misleading users and wasted time due to import/name/CLI mismatches is “High” until README and guides are corrected.
- Risk of user confusion on async usage is “High” due to top-level await in docs; fix by wrapping in `asyncio.run`.
- Risk from broken links and non-existent classes is “Medium” (usability and credibility).

## 5) Suggested Order of Execution

1) Fix README and high-severity guide issues (Ingestion, API Reference, Validation link).
2) Correct Caching Guide references.
3) Update Examples index and any remaining consistency items.
4) Optionally add `--list-exchanges` to CLI or adjust that part of the docs.

## 6) Acceptance Criteria Checklist

- No code snippet in docs references non-existent classes or functions.
- All CLI commands in docs are runnable against `rustybt/rustybt/__main__.py`.
- Async examples do not use bare `await`.
- README quick starts (backtest, ingestion, live) execute without import or CLI errors.
- All doc links are valid based on current repo.

## 7) Appendix: Quick Fix Snippets

- README CCXT import:
  ```python
  # Correct
  from rustybt.live.brokers import CCXTBrokerAdapter
  ```
- Unified ingestion CLI:
  ```bash
  rustybt ingest-unified yfinance \
    --bundle my-stocks \
    --symbols AAPL,MSFT,GOOGL \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --frequency 1d
  ```
- Async ingestion wrapper:
  ```python
  import asyncio, pandas as pd
  from rustybt.data.sources import DataSourceRegistry

  async def main():
      source = DataSourceRegistry.get_source("ccxt", exchange="binance")
      await source.ingest_to_bundle(
          bundle_name="crypto-hourly",
          symbols=["BTC/USDT", "ETH/USDT"],
          start=pd.Timestamp("2024-01-01"),
          end=pd.Timestamp("2024-12-31"),
          frequency="1h"
      )

  asyncio.run(main())
  ```

---

If you want, I can implement the doc changes as a set of targeted edits (README + guides), or add the optional `--list-exchanges` CLI to `ingest-unified`.
