# Enhancement Scope and Integration Strategy

## Enhancement Overview

**Enhancement Type:** Systematic transformation of existing backtesting platform into production-grade live trading system

**Scope:**
- Fork Zipline-Reloaded v3.x as foundation (currently at v3.0.5)
- Transform 10 core functional areas across 3 implementation tiers
- MVP (Epics 1-5): Foundation, Decimal arithmetic, modern data architecture, transaction costs, optimization
- Post-MVP (Epics 6-9): Live trading, Rust optimization, analytics, API layer

**Integration Impact Level:** **HIGH**

Core modules require substantial modification:
- **finance/** → Decimal arithmetic replacement (ledger, position, order, transaction)
- **data/** → Polars/Parquet data layer replacing bcolz
- **gens/** → Extended for live trading mode with real-time clock
- **New modules** → Live trading engine, broker integrations, RESTful API

## Integration Approach

### Code Integration Strategy

**Parallel Implementation (Epics 1-5):**
- Keep Zipline's float64 implementations alongside new Decimal variants
- Feature flags: `RUSTYBT_USE_DECIMAL`, `RUSTYBT_USE_POLARS`
- Gradual test migration from Zipline fixtures to RustyBT fixtures
- CI runs both legacy and new implementations until validation complete

**Additive Enhancement (Epics 6-9):**
- New modules for live trading, API layer, advanced analytics
- Integration hooks into existing algorithm execution lifecycle
- Maintain backward compatibility for pure backtesting use cases

### Database Integration

**Preserve:**
- SQLite asset database schema (Zipline ASSET_DB_VERSION 8)
- Asset table structure: equities, futures, exchanges, symbol_mappings

**Extend:**
- New tables for live trading:
  - `broker_connections`: API keys, connection configs
  - `live_positions`: Real-time position tracking with reconciliation timestamps
  - `order_audit_log`: Trade-by-trade audit trail (JSON structured logs)
  - `strategy_state`: Checkpoints for crash recovery

**Migrate:**
- Data bundles: bcolz → Parquet (one-time conversion utility)
- Provide `rustybt bundle migrate <bundle_name>` CLI command
- Support dual-format reads during transition period

### API Integration

**Preserve (Backtest API):**
- `initialize(context)`: Strategy setup
- `handle_data(context, data)`: Bar-by-bar processing
- `before_trading_start(context, data)`: Pre-market calculations
- `analyze(context, results)`: Post-backtest analysis

**Extend (Live Trading Hooks):**
- `on_order_fill(context, order, transaction)`: Real-time fill notifications
- `on_order_cancel(context, order, reason)`: Cancellation handling
- `on_order_reject(context, order, reason)`: Rejection handling
- `on_broker_message(context, message)`: Custom broker events

**Add (External Integration - Epic 9):**
- RESTful API for remote monitoring and control
- WebSocket API for real-time updates

### UI Integration

**N/A** - RustyBT remains a library, not an application
- Primary interface: Jupyter notebooks (same as Zipline)
- Optional: Web dashboard for live trading monitoring (Epic 9, lowest priority)

## Compatibility Requirements

### Existing API Compatibility

**BREAKING CHANGES** - RustyBT does not guarantee Zipline API compatibility (per PRD):
- Users must migrate strategies to use Decimal types for financial calculations
- Data bundle format changes (bcolz → Parquet)
- Some method signatures change (e.g., `order(asset, amount)` amount becomes Decimal)
- **Migration Guide**: Provide comprehensive migration documentation

### Database Schema Compatibility

**PARTIAL COMPATIBILITY:**
- ✅ Asset database schema preserved (can reuse existing `assets-8.sqlite`)
- ✅ Exchange calendar data compatible
- ❌ Bundle format requires migration (provide conversion tool)
- ❌ Adjustment format may change (Parquet-optimized storage)

### UI/UX Consistency

**N/A** - Library interface, not end-user application

### Performance Impact

**Target:** <30% overhead for Decimal vs. float64 (per NFR3)

**Mitigation Strategies:**
1. Profile bottlenecks after Python implementation complete (Epic 7)
2. Apply Rust optimization strategically to hot paths:
   - Decimal arithmetic operations (portfolio value, P&L calculations)
   - Data processing pipelines (resampling, aggregation)
   - Pipeline engine execution (factor computation loops)
3. Polars performance gains expected to offset some Decimal overhead (5-10x faster than pandas)

---
