# Live Trading Infrastructure

Production-ready infrastructure for deploying strategies to live markets with safety controls and state management.

## Overview

The live trading system enables strategies developed in backtesting to run in production with real capital. It provides broker integrations, real-time data streaming, position reconciliation, state management, and comprehensive safety controls.

### Key Features

- **Multiple Broker Support**: CCXT (100+ exchanges), Interactive Brokers, Binance, Bybit, Hyperliquid
- **Real-Time Streaming**: WebSocket data feeds for live market data
- **State Management**: Checkpointing and recovery for reliability
- **Position Reconciliation**: Sync with broker positions automatically
- **Circuit Breakers**: Automated risk controls and safety limits
- **Shadow Trading**: Parallel backtest validation against live execution
- **Paper Trading**: Simulated trading for strategy validation

### Architecture

```
┌──────────────────────────────────────────────────────┐
│             Trading Strategy (Your Code)              │
├──────────────────────────────────────────────────────┤
│            LiveTradingEngine                          │
│  ┌─────────┬──────────┬───────────┬───────────┐     │
│  │ Event   │  State   │Position   │ Circuit   │     │
│  │ Loop    │ Manager  │Reconciler │ Breakers  │     │
│  └─────────┴──────────┴───────────┴───────────┘     │
├──────────────────────────────────────────────────────┤
│       Broker Adapter (CCXT/IB/Binance/etc.)         │
├──────────────────────────────────────────────────────┤
│    ┌──────────────┬──────────────┐                  │
│    │   Orders     │  Market Data │                  │
│    │  REST API    │   WebSocket  │                  │
│    └──────────────┴──────────────┘                  │
├──────────────────────────────────────────────────────┤
│         Live Market / Exchange / Broker              │
└──────────────────────────────────────────────────────┘
```

## Quick Navigation

### Core Infrastructure
- **[Streaming Architecture](streaming/architecture.md)** - Real-time data streaming design
- **[Exchange-Specific Streams](streaming/binance.md)** - Binance, Bybit, Hyperliquid, CCXT

### State Management
- **[State Management](state/management.md)** - Checkpointing and recovery
- **[Position Reconciliation](state/reconciliation.md)** - Syncing with broker positions
- **[Recovery Procedures](state/recovery.md)** - Handling failures and restarts

### Safety & Risk Controls
- **[Circuit Breakers](safety/circuit-breakers.md)** - Automated trading halts
- **[Position Limits](safety/limits.md)** - Risk limits and constraints
- **[Monitoring](safety/monitoring.md)** - Health checks and alerts

### Deployment
- **[Setup Guide](deployment/setup.md)** - Production deployment
- **[Configuration](deployment/configuration.md)** - Environment and settings
- **[Best Practices](deployment/best-practices.md)** - Production recommendations

## Quick Start

### Basic Live Trading

```python
# Code example removed - API does not exist
```

## Error Handling

### Graceful Shutdown

```python
# Code example removed - API does not exist
```

### Automatic Recovery

```python
# Code example removed - API does not exist
```

## Monitoring

### Health Checks

```python
# Code example removed - API does not exist
```

### 4. Monitor Closely

```python
# Code example removed - API does not exist
```

### ❌ Ignoring State Management

```python
# Code example removed - API does not exist
```

## Examples

See `examples/live_trading/` for complete examples:

- `paper_trading_example.py` - Basic paper trading
- `binance_live_trading.py` - Binance integration
- `ib_live_trading.py` - Interactive Brokers
- `shadow_trading_example.py` - Shadow backtest validation
- `production_deployment.py` - Full production setup

## See Also

- [Main Live Trading API](../live-trading-api.md)
- [Optimization Documentation](../optimization/README.md)
- [Analytics Documentation](../analytics/README.md)
- [Broker Setup Guide](../../guides/broker-setup-guide.md)

## Support

- **Issues**: [GitHub Issues](https://github.com/bmad-dev/rustybt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/bmad-dev/rustybt/discussions)
- **Documentation**: [Full API Reference](https://rustybt.readthedocs.io)

## ⚠️ Risk Warning

**Live trading involves real financial risk. You can lose money.**

- Always test thoroughly in paper trading and testnets
- Start with small capital
- Use all safety controls
- Monitor closely
- Never risk more than you can afford to lose
