# RustyBT Examples

This directory contains example scripts demonstrating various features of RustyBT.

## Data Ingestion Examples

### `ingest_yfinance.py`
Demonstrates ingesting stock data from Yahoo Finance.

```bash
python examples/ingest_yfinance.py
```

**What it demonstrates**:
- Using DataSourceRegistry to get a data source
- Ingesting daily stock data
- Accessing bundle metadata
- Quality metrics (missing data %, quality score)

---

### `ingest_ccxt.py`
Demonstrates ingesting cryptocurrency data from Binance via CCXT.

```bash
python examples/ingest_ccxt.py
```

**What it demonstrates**:
- CCXT integration for crypto data
- Hourly data ingestion
- Working with crypto symbols (BTC/USDT format)
- Bundle metadata for crypto data

---

## Performance Examples

### `backtest_with_cache.py`
Demonstrates the performance benefits of caching.

```bash
python examples/backtest_with_cache.py
```

**What it demonstrates**:
- Cache miss vs cache hit performance
- 10-20x speedup for repeated backtests
- Cache statistics tracking
- When to use caching vs direct fetches

---

## Requirements

All examples require:
```bash
pip install rustybt
```

Some examples require additional dependencies:
- `ingest_ccxt.py`: Requires CCXT (`pip install ccxt`)
- `ingest_polygon.py`: Requires Polygon API key

---

## Running Examples

### Quick Start

```bash
# Install RustyBT
pip install rustybt

# Run an example
python examples/ingest_yfinance.py
```

### Expected Output

All examples print progress and results:
```
============================================================
Yahoo Finance Data Ingestion Example
============================================================

[1/4] Initializing YFinance data source...
✓ Data source initialized

[2/4] Ingesting data...
  Bundle: yfinance-example
  Symbols: AAPL, MSFT, GOOGL
  Period: 2023-01-01 to 2023-12-31
  Frequency: 1d
✓ Data ingested to: ~/.rustybt/bundles/yfinance-example

[3/4] Loading bundle metadata...
✓ Metadata loaded

[4/4] Bundle Summary:
  Symbols: 3
  Date range: 2023-01-01 to 2023-12-31
  Rows: 756
  Size: 0.12 MB
  Quality score: 98.50%
  Missing data: 1.50%

============================================================
✓ Bundle created successfully!
============================================================
```

---

## Example Categories

### Beginner
- `ingest_yfinance.py` - Basic data ingestion
- `backtest_with_cache.py` - Understanding caching

### Intermediate
- `ingest_ccxt.py` - Multi-exchange crypto data

### Advanced
- Optimization (grid/random/bayesian/genetic)
- Live trading with PaperBroker/CCXT
- Latency/slippage/borrow cost modeling
- Parallel optimization and report generation

---

## Troubleshooting

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'rustybt'`

**Solution**: Install RustyBT: `pip install rustybt`

---

### API Rate Limits

**Error**: `RateLimitExceeded: Too many requests`

**Solution**: Add delays between requests or use caching:
```python
await asyncio.sleep(1)  # 1 second delay
```

---

### No Data Found

**Error**: `NoDataAvailableError: Symbol AAPL has no data`

**Possible causes**:
- Market holiday (no trading that day)
- Weekend/outside market hours
- Symbol delisted or invalid

---

## Contributing Examples

We welcome example contributions! Please:
1. Follow the existing format (docstring, main(), progress output)
2. Include error handling and user-friendly messages
3. Test the example before submitting PR
4. Update this README with a description

---

## Additional Resources

### 📖 Quick Start
- [Documentation Index](../docs/INDEX.md) - Complete documentation catalog with learning paths

### 📚 User Guides

**Data & Backtesting:**
- [Data Ingestion Guide](../docs/guides/data-ingestion.md) - Fetching and storing market data
- [Caching Guide](../docs/guides/caching-guide.md) - Optimizing backtest performance
- [Data Validation Guide](../docs/guides/data-validation.md) - Quality checks and validation
- [Migration Guide](../docs/guides/migrating-to-unified-data.md) - Upgrading from legacy data systems

**Live Trading:**
- [Broker Setup Guide](../docs/guides/broker-setup-guide.md) - Configuring brokers (Binance, Bybit, IB, etc.)
- [WebSocket Streaming Guide](../docs/guides/websocket-streaming-guide.md) - Real-time market data
- [Live vs Backtest Data](../docs/guides/live-vs-backtest-data.md) - Understanding data modes

**Advanced Topics:**
- [Pipeline API Guide](../docs/guides/pipeline-api-guide.md) - Factor-based strategies
- [Exception Handling Guide](../docs/guides/exception-handling.md) - Error handling patterns
- [Audit Logging Guide](../docs/guides/audit-logging.md) - Structured logging
- [Type Hinting Guide](../docs/guides/type-hinting.md) - Type safety best practices

### 🔧 API References

**Data Layer:**
- [DataSource API](../docs/api/datasource-api.md) - Data ingestion and bundles
- [Caching API](../docs/api/caching-api.md) - Cache configuration and usage
- [Bundle Metadata API](../docs/api/bundle-metadata-api.md) - Bundle information

**Live Trading:**
- [Live Trading API](../docs/api/live-trading-api.md) - LiveTradingEngine and broker adapters
- [Order Types](../docs/api/order-types.md) - Available order types and parameters

**Analytics:**
- [Analytics API](../docs/api/analytics-api.md) - Performance analysis and reporting
- [Finance API](../docs/api/finance-api.md) - Commission, slippage, and costs

**Optimization:**
- [Optimization API](../docs/api/optimization-api.md) - Parameter optimization algorithms
