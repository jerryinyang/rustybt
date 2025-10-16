# Live Trading API Reference

⚠️ **Note:** The API reference documentation for live trading is currently being reorganized to ensure all code examples use actual working implementations.

In the meantime, please refer to our comprehensive **user guides** which contain complete, tested examples for all live trading functionality:

---

## 📚 **Complete Live Trading Documentation**

### Getting Started with Live Trading

- **[Broker Setup Guide](../../guides/broker-setup-guide.md)** - Complete setup for all supported brokers
  - PaperBroker (testing without real capital)
  - Binance (crypto spot and futures)
  - Bybit (derivatives trading)
  - Hyperliquid (decentralized perpetuals)
  - Interactive Brokers (traditional markets)
  - CCXT Generic (100+ exchanges)

### Real-Time Data Streaming

- **[WebSocket Streaming Guide](../../guides/websocket-streaming-guide.md)** - Real-time market data
  - WebSocket connection management
  - Bar aggregation from tick data
  - Multiple stream handling
  - Performance optimization

### Production Deployment

- **[Deployment Guide](../../guides/deployment-guide.md)** - Production deployment strategies
  - Environment setup
  - Configuration management
  - Monitoring and logging
  - Scaling considerations

- **[Production Checklist](../../guides/production-checklist.md)** - Pre-deployment safety checklist
  - Risk management verification
  - Circuit breaker configuration
  - Position limits
  - Emergency procedures

### Data Considerations

- **[Live vs Backtest Data Guide](../../guides/live-vs-backtest-data.md)** - Data differences and considerations
  - Real-time vs historical data
  - Latency management
  - Data quality checks

---

## 🔧 **Source Code Reference**

For implementation details, refer to the actual broker adapter source code:

### Broker Adapters

Located in `rustybt/live/brokers/`:

- `paper_broker.py` - Simulated broker for testing
- `binance_adapter.py` - Binance exchange integration
- `bybit_adapter.py` - Bybit exchange integration
- `hyperliquid_adapter.py` - Hyperliquid DEX integration
- `ib_adapter.py` - Interactive Brokers integration
- `ccxt_adapter.py` - Generic CCXT exchange wrapper

### Safety Systems

Located in `rustybt/live/`:

- `engine.py` - Live trading engine with built-in safety controls
- `reconciler.py` - Position reconciliation with broker
- `state_manager.py` - State persistence and recovery
- `scheduler.py` - Market-aware scheduling

### Circuit Breakers & Risk Controls

The live trading engine includes built-in safety mechanisms:

```python
from rustybt.live.engine import LiveTradingEngine

# Circuit breakers are configured in the engine
engine = LiveTradingEngine(
    strategy=my_strategy,
    broker=broker,
    max_daily_loss=Decimal("1000"),      # Daily loss limit
    max_position_value=Decimal("50000"),  # Per-position limit
    max_total_exposure=Decimal("100000"), # Total exposure limit
)
```

**See `rustybt/live/engine.py` source code for complete implementation details.**

---

## 📖 **API Reference (Under Development)**

Detailed API reference documentation for the following modules is being prepared with tested code examples:

- [ ] Live Trading Engine API
- [ ] Broker Adapter Interface
- [ ] Circuit Breaker Configuration
- [ ] Position Reconciliation API
- [ ] State Management API
- [ ] Real-Time Data Streaming API

**Expected completion:** Q1 2025

---

## 🆘 **Support**

- **Questions?** See our [Troubleshooting Guide](../../guides/troubleshooting.md)
- **Issues?** Report on [GitHub Issues](https://github.com/bmad-sim/rustybt/issues)
- **Community:** Join discussions on GitHub Discussions

---

## ⚠️ **Safety Notice**

Live trading involves real financial risk. Always:

1. ✅ Test thoroughly with PaperBroker first
2. ✅ Start with small position sizes
3. ✅ Configure appropriate circuit breakers and limits
4. ✅ Monitor positions and P&L actively
5. ✅ Have emergency shutdown procedures in place
6. ✅ Review the [Production Checklist](../../guides/production-checklist.md) before going live

**Never deploy to production without comprehensive testing and risk controls.**

---

*For the most up-to-date information, always refer to the guides linked above and the source code implementations.*
