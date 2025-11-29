# Source Tree

## RustyBT Directory Structure

```
rustybt/                                  # Root package
├── __init__.py
├── __main__.py                          # CLI entry point
├── version.py
│
├── finance/                             # Financial calculations (Decimal)
│   ├── __init__.py
│   ├── decimal/                         # NEW: Decimal-based modules
│   │   ├── __init__.py
│   │   ├── ledger.py                   # DecimalLedger
│   │   ├── position.py                 # DecimalPosition
│   │   ├── transaction.py              # DecimalTransaction
│   │   ├── blotter.py                  # DecimalBlotter
│   │   └── context.py                  # Decimal precision config
│   ├── commission.py                    # EXTEND: Decimal commission models
│   ├── slippage.py                      # EXTEND: Decimal slippage models
│   ├── execution.py                     # EXTEND: Advanced order types
│   ├── controls.py                      # KEEP: Trading controls (from Zipline)
│   ├── trading.py                       # KEEP: Trading calendar integration
│   └── metrics/                         # EXTEND: Decimal metrics
│       ├── __init__.py
│       ├── core.py                      # Decimal performance metrics
│       └── tracker.py                   # Decimal metrics tracker
│
├── data/                                # Data management (Polars)
│   ├── __init__.py
│   ├── polars/                          # NEW: Polars-based data layer
│   │   ├── __init__.py
│   │   ├── parquet_daily_bars.py       # PolarsParquetDailyReader
│   │   ├── parquet_minute_bars.py      # PolarsParquetMinuteReader
│   │   ├── data_portal.py              # PolarsDataPortal
│   │   └── catalog.py                  # DataCatalog with caching
│   ├── adapters/                        # NEW: Data source adapters
│   │   ├── __init__.py
│   │   ├── base.py                     # BaseDataAdapter
│   │   ├── ccxt_adapter.py             # CCXTDataAdapter
│   │   ├── yfinance_adapter.py         # YFinanceAdapter
│   │   ├── csv_adapter.py              # CSVAdapter
│   │   └── registry.py                 # Adapter registration
│   ├── bundles/                         # KEEP: Bundle management (from Zipline)
│   │   ├── __init__.py
│   │   ├── core.py                     # EXTEND: Add Parquet bundle writer
│   │   ├── csvdir.py                   # KEEP: CSV bundle support
│   │   └── migration.py                # NEW: bcolz → Parquet migration
│   ├── bar_reader.py                    # KEEP: Abstract BarReader interface
│   ├── adjustments.py                   # KEEP: Corporate actions (from Zipline)
│   └── resample.py                      # EXTEND: Polars-based resampling
│
├── live/                                # NEW: Live trading engine
│   ├── __init__.py
│   ├── engine.py                        # LiveTradingEngine
│   ├── reconciler.py                    # PositionReconciler (broker sync)
│   ├── state_manager.py                 # StateManager (checkpointing)
│   ├── scheduler.py                     # TradingScheduler (market triggers)
│   ├── brokers/                         # Broker adapters
│   │   ├── __init__.py
│   │   ├── base.py                     # BrokerAdapter (abstract)
│   │   ├── ccxt_adapter.py             # CCXTAdapter (100+ exchanges)
│   │   ├── ib_adapter.py               # IBAdapter (Interactive Brokers)
│   │   ├── binance_adapter.py          # BinanceAdapter (native SDK)
│   │   ├── bybit_adapter.py            # BybitAdapter (native SDK)
│   │   ├── hyperliquid_adapter.py      # HyperliquidAdapter (DEX)
│   │   └── paper_broker.py             # PaperBroker (simulation)
│   └── streaming/                       # NEW: WebSocket data feeds (Epic 6)
│       ├── __init__.py
│       ├── base.py                     # BaseStreamAdapter
│       └── binance_stream.py           # BinanceStreamAdapter
│
├── assets/                              # Asset management (extended)
│   ├── __init__.py
│   ├── assets.py                        # EXTEND: Add Cryptocurrency class
│   ├── asset_db_schema.py              # EXTEND: Add cryptocurrencies table
│   ├── asset_writer.py                 # EXTEND: Write crypto assets
│   ├── asset_finder.py                 # KEEP: AssetFinder (from Zipline)
│   ├── futures.py                       # KEEP: Futures contracts
│   └── continuous_futures.py           # KEEP: Continuous futures
│
├── algorithm.py                         # EXTEND: TradingAlgorithm with live hooks
├── api.py                               # EXTEND: Add live trading API functions
│
├── pipeline/                            # KEEP: Pipeline framework (from Zipline)
│   ├── __init__.py
│   ├── engine.py                        # EXTEND: Polars-compatible pipeline engine
│   ├── factors/                         # KEEP: Factor library
│   ├── filters/                         # KEEP: Filter library
│   └── classifiers/                     # KEEP: Classifier library
│
├── gens/                                # EXTEND: Event generators
│   ├── __init__.py
│   ├── tradesimulation.py              # KEEP: Simulation mode (from Zipline)
│   ├── live_simulation.py              # NEW: Live trading mode
│   └── clock.py                         # NEW: Unified clock (sim + live)
│
├── utils/                               # KEEP: Shared utilities (from Zipline)
│   ├── __init__.py
│   ├── events.py                        # KEEP: Event system
│   ├── calendar_utils.py               # EXTEND: 24/7 crypto calendars
│   ├── validation.py                    # EXTEND: Decimal validation
│   └── security.py                      # NEW: Credential encryption
│
├── optimization/                        # DUAL PURPOSE: Strategy optimization (Epic 5) + Performance optimization (Epic X4)
│   ├── __init__.py
│   │
│   ├── # === Epic 5: Strategy Optimization ===
│   ├── optimizer.py                     # Optimizer framework
│   ├── parallel_optimizer.py            # Parallel execution (MODIFIED in X4)
│   ├── search/                          # Search algorithms
│   │   ├── __init__.py
│   │   ├── grid_search.py              # Grid search optimization
│   │   ├── random_search.py            # Random search
│   │   ├── bayesian_search.py          # Bayesian optimization
│   │   └── genetic_algorithm.py        # Genetic algorithms
│   ├── walk_forward.py                  # Walk-forward optimization
│   ├── monte_carlo.py                   # Monte Carlo simulation
│   ├── sensitivity.py                   # Parameter sensitivity analysis
│   │
│   ├── # === Epic X4: Performance Optimization (Phase 6A) ===
│   ├── caching.py                       # NEW: CachedAssetList, PreGroupedData (70% speedup)
│   ├── dataportal_ext.py                # NEW: HistoryCache multi-tier LRU (20-25% speedup)
│   ├── bundle_pool.py                   # NEW: BundleConnectionPool singleton (8-12% speedup)
│   ├── cache_invalidation.py            # NEW: BundleVersionMetadata, SHA256 tracking
│   └── config.py                        # NEW: OptimizationConfig with feature flags
│
├── api_layer/                           # NEW: RESTful/WebSocket API (Epic 9)
│   ├── __init__.py
│   ├── app.py                           # FastAPI application
│   ├── routes/                          # API endpoints
│   │   ├── __init__.py
│   │   ├── strategies.py               # Strategy management
│   │   ├── portfolio.py                # Portfolio queries
│   │   ├── orders.py                   # Order management
│   │   └── data.py                     # Data catalog access
│   ├── websocket.py                     # WebSocket server
│   └── auth.py                          # Authentication/authorization
│
├── analytics/                           # NEW: Advanced analytics (Epic 8)
│   ├── __init__.py
│   ├── attribution.py                   # Performance attribution
│   ├── risk.py                          # Risk metrics (VaR, CVaR, beta)
│   ├── trade_analysis.py               # Trade-level analysis
│   └── reports.py                       # Report generation
│
├── testing/                             # KEEP: Testing utilities (from Zipline)
│   ├── __init__.py
│   ├── fixtures.py                      # EXTEND: Add Decimal fixtures
│   ├── core.py                          # KEEP: Test utilities
│   └── property_tests.py               # NEW: Hypothesis property tests
│
├── cli/                                 # EXTEND: CLI commands
│   ├── __init__.py
│   ├── commands.py                      # EXTEND: Add RustyBT commands
│   ├── run.py                           # KEEP: Run backtest command
│   ├── bundle.py                        # EXTEND: Add migration command
│   └── live.py                          # NEW: Live trading commands
│
└── benchmarks/                          # NEW: Performance benchmarking infrastructure (Epic X4)
    ├── __init__.py
    ├── models.py                        # PerformanceThreshold, BenchmarkResult dataclasses
    ├── profiling.py                     # Profiling infrastructure (cProfile, line_profiler)
    ├── reporter.py                      # Report generation with percentage contributions
    ├── threshold.py                     # 5% minimum improvement threshold validation
    ├── sequential.py                    # Sequential optimization evaluation
    ├── comparisons.py                   # Functional equivalence testing
    └── baseline/                        # Pure Python baseline implementations
        ├── __init__.py
        ├── python_indicators.py         # Pure Python SMA, EMA (replacing Rust)
        ├── python_data_ops.py           # Pure Python data operations
        └── python_decimal_ops.py        # Pure Python Decimal operations
```

## Directories Marked for Removal (Epic X4 - Phase 4)

```
rust/                                    # TO BE REMOVED - Phase 4 of Epic X4
├── Cargo.toml                          # Rust build configuration (REMOVE)
├── src/
│   ├── lib.rs                          # Rust library entry (REMOVE)
│   ├── indicators.rs                   # SMA, EMA, rolling operations (REMOVE - <1% impact)
│   ├── data_ops.rs                     # Window slice, fillna (REMOVE - <1% impact)
│   └── decimal_ops.rs                  # Decimal operations (REMOVE - <1% impact)
└── target/                              # Rust build artifacts (REMOVE)
```

**Removal Rationale**: Phase 3 profiling revealed Rust micro-operations contribute <2% to end-to-end workflow performance. Real bottlenecks are in data access layer (87% user code overhead, 58.4% DataPortal overhead). See `specs/002-performance-benchmarking-optimization/profiling-results/` for detailed analysis.

## Integration with Zipline Structure

**Preserved Zipline Modules:**
- `algorithm.py`: Extended with live trading hooks
- `assets/`: Extended with cryptocurrency support
- `data/bundles/`: Extended with Parquet support
- `pipeline/`: Extended with Polars compatibility
- `utils/`: Extended with additional utilities
- `testing/`: Extended with Decimal fixtures

**New RustyBT Modules:**
- `finance/decimal/`: Decimal arithmetic layer
- `data/polars/`: Polars/Parquet data layer
- `data/adapters/`: Data source adapters
- `live/`: Live trading engine
- `optimization/`: Optimization framework
- `api_layer/`: REST/WebSocket API
- `analytics/`: Advanced analytics
- `benchmarks/`: Performance benchmarking infrastructure

**Migration Path:**
1. Epics 1-5: Parallel implementation (Zipline float + RustyBT Decimal coexist)
2. Epic 6: Add live trading (no Zipline equivalent)
3. Epic 7: Performance optimization (profiling-driven, pure Python)
4. Epic 8-9: Add analytics and API (additive features)

---
