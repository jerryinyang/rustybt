# Next Steps

## UX Expert Prompt

**Note**: UX/UI design goals were intentionally skipped as RustyBT is a Python library framework without graphical user interface. The focus is on programmatic API design, Jupyter notebook integration, and CLI usability rather than visual design.

If UX analysis is needed for developer experience (DX), Jupyter notebook workflows, or API ergonomics, the UX Expert can review this PRD focusing on:
- Python API design patterns and usability
- Jupyter notebook integration and interactive workflows
- CLI command design and documentation structure
- Error message clarity and developer guidance

## Architect Prompt

You are the Architect for RustyBT, a production-grade Python/Rust trading platform. Review the attached PRD ([docs/prd.md](docs/prd.md)) and [docs/brief.md](docs/brief.md), then design the architecture for **MVP scope (Epics 1-5)** with extensibility for Epics 6-9.

**Your tasks**:
1. Design system architecture for Epics 1-5 (Foundation, Decimal, Data Catalog, Transaction Costs, Optimization)
2. Define module structure, interfaces, and data flows
3. Specify technology integration (Polars, Parquet, SQLite, Decimal, PyO3 preparation)
4. Design data catalog with intelligent caching system
5. Plan for future extensibility (live trading, Rust optimization, APIs)
6. Identify technical risks and mitigation strategies
7. Create architecture documentation with diagrams

**Key considerations**:
- Fork Zipline-Reloaded foundation (88.26% test coverage) and extend, don't rebuild
- Python-first: Pure Python implementation, Rust only after profiling identifies bottlenecks (Epic 7)
- Temporal isolation is non-negotiable: prevent lookahead bias at architectural level
- Design for testing: Every component must be testable in isolation
- Monorepo structure: Python package + future Rust modules + docs + tests

**Start with**: Epic 1 (Foundation & Core Infrastructure) detailed design, treating it as the architectural foundation for all subsequent epics.
