# Goals and Background Context

## Goals

- Deliver financial-grade Decimal arithmetic throughout the platform to eliminate float rounding errors and ensure audit-compliant financial accuracy
- Build unified data catalog with intelligent local caching enabling instant retrieval for repeated backtests using the same data
- Enable production-grade live trading with 5+ direct broker integrations and seamless backtest-to-live transition with >99% behavioral correlation
- Achieve comprehensive temporal isolation guarantees preventing lookahead bias and data leakage
- Provide strategic Rust performance optimization targeting <30% overhead vs. float baseline through profiling-driven optimization of bottlenecks (Decimal arithmetic, loops, subprocesses, data processing)

## Background Context

RustyBT addresses critical gaps in existing Python backtesting frameworks that prevent production deployment. Current tools like Zipline and Backtrader use float for financial calculations, creating audit-compliance issues and materially incorrect results. They also lack rigorous temporal isolation guarantees, use obsolete data architectures (HDF5), and provide minimal live trading support. By forking Zipline-Reloaded's stable foundation (88.26% test coverage) and implementing 10 core functional enhancements across 3 implementation tiers, RustyBT bridges the gap between academic backtesting tools and production-ready live trading systems.

The platform targets individual quantitative traders and small teams requiring audit-compliant accuracy, fast iteration cycles with cached data, and self-hosted deployment without vendor lock-in. Development follows milestone-driven progress organized by implementation complexity rather than arbitrary timelines.

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-09-30 | 1.0 | Initial PRD draft | PM John |

---
