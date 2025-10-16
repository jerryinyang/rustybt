# Epic 3: Modern Data Architecture - MVP Data Sources

**Expanded Goal**: Replace Zipline-Reloaded's HDF5 storage with modern Polars/Parquet-based unified data catalog featuring intelligent local caching. Implement core data source adapters for MVP validation: CCXT (crypto exchanges), YFinance (stocks/ETFs), and CSV (custom data import). Add multi-resolution time series support with OHLCV validation. WebSocket streaming, data API providers (Polygon, Alpaca, Alpha Vantage), and additional adapters deferred to Epic 6. Testing, examples, and documentation integrated throughout.

---

## Story 3.1: Design Unified Data Catalog Architecture

**As a** developer,
**I want** architectural design for Polars/Parquet data catalog with local caching system,
**so that** implementation follows a coherent plan with clear interfaces and data flows.

### Acceptance Criteria

1. Architecture diagram created showing catalog components (SQLite metadata, Parquet storage, Polars query layer, cache manager)
2. Data schema designed for Parquet storage (OHLCV + metadata columns with Decimal types)
3. Metadata schema designed for SQLite catalog (symbols, date ranges, resolutions, checksums, backtest linkage)
4. Caching strategy documented (two-tier: in-memory Polars DataFrame + disk Parquet)
5. Cache key design specified (how to identify "same data" across backtests)
6. Cache invalidation strategy defined (when upstream data changes detected)
7. Interface contracts defined for DataCatalog, CacheManager, DataAdapter base class
8. Migration plan documented from HDF5 to Parquet (conversion utilities)
9. Architecture documentation saved to docs/architecture/data-catalog.md
10. Design reviewed and approved before implementation begins

---

## Story 3.2: Implement Parquet Storage Layer with Metadata Catalog

**As a** quantitative trader,
**I want** price data stored in Parquet format with SQLite metadata catalog,
**so that** data storage is efficient, queryable, and interoperable with modern tools.

### Acceptance Criteria

1. Parquet storage directory structure created (organized by symbol, resolution, date range)
2. Parquet schema implemented with Decimal types for OHLCV columns
3. SQLite metadata database created with tables for datasets, symbols, date_ranges, checksums
4. Write path implemented: OHLCV data → Parquet file + metadata entry in SQLite
5. Read path implemented: query metadata → locate Parquet files → load via Polars
6. Compression enabled (Snappy or ZSTD) for Parquet files (50-80% size reduction vs. HDF5)
7. Metadata indexing implemented for fast queries (symbol, date range, resolution)
8. Dataset versioning supported (track schema version for backward compatibility)
9. Tests validate write → read roundtrip maintains Decimal precision
10. Migration utility created to convert existing HDF5 bundles to Parquet

---

## Story 3.3: Implement Intelligent Local Caching System

**As a** quantitative trader,
**I want** intelligent caching that links price data to backtests,
**so that** subsequent backtests using the same data retrieve it instantly (<1 second) without re-fetching from API.

### Acceptance Criteria

1. Cache metadata schema extended with backtest_id, cache_timestamp, last_accessed fields
2. Cache key generation implemented (based on symbols, date range, resolution, data source)
3. Cache lookup implemented: check if requested data exists in cache with valid checksum
4. Cache hit returns data from Parquet in <1 second for typical dataset
5. Cache miss triggers data fetch from adapter, stores in cache with backtest linkage
6. Two-tier caching: hot data in-memory (Polars DataFrame), cold data on disk (Parquet)
7. Cache eviction policy implemented (LRU or size-based, configurable max cache size)
8. Cache statistics tracked (hit rate, miss rate, storage size) and queryable via API
9. Tests validate cache hit/miss scenarios and performance targets
10. Documentation explains caching behavior and configuration options

---

## Story 3.4: Implement Base Data Adapter Framework

**As a** developer,
**I want** extensible base adapter class with standardized interface,
**so that** new data sources can be integrated consistently with minimal code.

### Acceptance Criteria

1. BaseDataAdapter abstract class created with required methods (fetch, validate, standardize)
2. Adapter interface defined: fetch(symbols, start_date, end_date, resolution) → DataFrame
3. Standardization layer implemented: convert provider-specific formats to unified OHLCV schema
4. Validation layer integrated: OHLCV relationship checks, outlier detection, temporal consistency
5. Error handling standardized across adapters (network errors, rate limits, invalid data)
6. Retry logic with exponential backoff for transient failures
7. Rate limiting support (configurable per-adapter to respect API limits)
8. Adapter registration system implemented (discover and load adapters dynamically)
9. Tests validate adapter interface compliance and error handling
10. Developer guide created for implementing new adapters

---

## Story 3.5: Implement CCXT Data Adapter (Priority: MVP - Crypto)

**As a** quantitative trader,
**I want** CCXT adapter for 100+ crypto exchanges,
**so that** I can backtest crypto strategies with data from Binance, Coinbase, Kraken, etc.

### Acceptance Criteria

1. CCXT library integrated (v4.x+) with dependency added to requirements
2. CCXTAdapter implements BaseDataAdapter interface
3. Exchange selection supported (Binance, Coinbase, Kraken, etc. via CCXT unified API)
4. OHLCV data fetched via CCXT `fetch_ohlcv()` method
5. Multiple resolutions supported (1m, 5m, 15m, 1h, 4h, 1d)
6. Rate limiting configured per exchange (respect CCXT rate limit metadata)
7. Data standardization converts CCXT format to unified schema with Decimal precision
8. Error handling covers exchange-specific issues (maintenance, delisted pairs)
9. Integration tests fetch live data from 3+ exchanges and validate schema
10. Example notebook demonstrates crypto backtest using CCXT data

---

## Story 3.6: Implement YFinance Data Adapter (Priority: MVP - Stocks/ETFs)

**As a** quantitative trader,
**I want** YFinance adapter for free stock/ETF/forex data,
**so that** I can backtest equity strategies without requiring paid data subscriptions.

### Acceptance Criteria

1. yfinance library integrated with dependency added to requirements
2. YFinanceAdapter implements BaseDataAdapter interface
3. Stock, ETF, forex symbol support (e.g., AAPL, SPY, EURUSD=X)
4. Multiple resolutions supported (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)
5. Dividend and split data fetched separately (for adjustment calculations)
6. Data standardization converts yfinance format to unified schema with Decimal precision
7. Error handling covers invalid symbols, delisted tickers, data gaps
8. Rate limiting implemented to avoid YFinance blocking (conservative delays)
9. Integration tests fetch live data for 5+ tickers and validate schema
10. Example notebook demonstrates equity backtest using YFinance data

---

## Story 3.7: Implement CSV Data Adapter with Schema Mapping (Priority: MVP)

**As a** quantitative trader,
**I want** flexible CSV import with custom schema mapping,
**so that** I can use proprietary or custom data sources not available via APIs.

### Acceptance Criteria

1. CSVAdapter implements BaseDataAdapter interface
2. Schema mapping configuration supported (map CSV columns to OHLCV fields)
3. Date parsing flexible (multiple formats supported: ISO8601, MM/DD/YYYY, epoch timestamps)
4. Delimiter detection (comma, tab, semicolon, pipe)
5. Header row handling (with or without headers, custom header names)
6. Data type inference with Decimal conversion for price columns
7. Timezone specification supported (convert to UTC internally)
8. Missing data handling (skip rows, interpolate, or fail based on configuration)
9. Tests validate various CSV formats (different delimiters, date formats, missing headers)
10. Example CSV files provided with documentation showing supported formats

---

## Story 3.8: Implement Multi-Resolution Aggregation with OHLCV Validation

**As a** quantitative trader,
**I want** automatic aggregation from high-resolution to low-resolution data with validation,
**so that** I can use 1-minute data to generate daily bars with confidence in accuracy.

### Acceptance Criteria

1. Aggregation functions implemented (minute → hourly, hourly → daily, daily → weekly/monthly)
2. OHLCV aggregation logic: Open=first, High=max, Low=min, Close=last, Volume=sum
3. OHLCV relationship validation post-aggregation (High ≥ Low, High ≥ Open/Close, Low ≤ Open/Close)
4. Timezone handling during aggregation (align to trading session boundaries, not calendar days)
5. Gap detection during aggregation (warn if missing data would make aggregation unreliable)
6. Performance optimized using Polars lazy evaluation and parallel aggregation
7. Validation detects outliers (price spikes >3 standard deviations flagged for review)
8. Temporal consistency checks (timestamps sorted, no duplicates, no future data)
9. Tests validate aggregation accuracy with known-correct examples
10. Property-based tests ensure aggregation invariants (e.g., aggregated volume == sum of source volumes)

---
