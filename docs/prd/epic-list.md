# Epic List

## MVP Scope (Epics 1-5): Foundation and Core Differentiation

**Epic 1: Foundation & Core Infrastructure**
Establish project setup, fork integration, CI/CD pipeline, and enhanced backtest engine with extended order types and performance metrics - delivering a functional enhanced backtesting platform with integrated testing, examples, and documentation.

**Epic 2: Financial Integrity - Decimal Arithmetic**
Replace float with Decimal throughout all financial calculations with configurable precision, property-based testing validation, and performance baseline benchmarking. Testing, examples, and documentation integrated throughout.

**Epic 3: Modern Data Architecture - MVP Data Sources**
Implement Polars/Parquet unified data catalog with intelligent local caching, and core data source adapters: CCXT (crypto), YFinance (stocks/ETFs), CSV (custom data import). Multi-resolution support and OHLCV validation included. Testing, examples, and documentation integrated throughout.

**Epic 4: Enhanced Transaction Costs & Multi-Strategy Portfolio**
Build realistic transaction cost modeling and multi-strategy portfolio management system with capital allocation algorithms. Testing, examples, and documentation integrated throughout.

**Epic 5: Strategy Optimization & Robustness Testing**
Implement parameter search algorithms with parallel processing, walk-forward optimization framework, parameter sensitivity analysis, and Monte Carlo simulation tools. Testing, examples, and documentation integrated throughout.

---

## Out of MVP Scope (Epics 6-9): Production Deployment and Scale

**Epic 6: Live Trading Engine & Broker Integrations**
Build production-ready live trading engine with state management, scheduled calculations, paper trading mode, and direct integrations for 5+ brokers. Includes data API providers and WebSocket streaming adapters deferred from Epic 3. Testing, examples, and documentation integrated throughout.

**Epic 7: Performance Optimization - Rust Integration**
Profile Python implementation to identify bottlenecks (Decimal arithmetic, loops, subprocesses, data processing), then reimplement hot paths in Rust for performance. Target <30% overhead vs. float baseline. Testing, benchmarking, and documentation integrated throughout.

**Epic 8: Analytics & Production Readiness**
Implement Jupyter notebook integration, programmatic reporting, advanced analytics (performance attribution, risk metrics, trade analysis), comprehensive security hardening (audit logging, type safety, credential encryption), and production deployment guide. Testing and documentation integrated throughout.

**Epic 9: RESTful API & WebSocket Interface (Lowest Priority)**
Build FastAPI REST API and WebSocket interface for remote strategy execution and real-time monitoring. Optional - evaluate necessity after Epic 6 live trading validates scheduled/triggered operations sufficiency. Testing and documentation integrated throughout.

---

## Documentation & Knowledge Management

**Epic 10: Comprehensive Framework Documentation**
Create exhaustive documentation covering 90%+ of the framework's functionality, organized by major subsystems matching the code structure, including all classes, methods, functions, workflows, and usage examples. Addresses current sparse API documentation that only covers Advanced Order Types, Caching API, and Bundle Metadata API.

---
