# rustybt Validation Framework

The rustybt Validation Framework provides a systematic approach to verify rustybt's correctness through comparison with [Backtrader](https://www.backtrader.com/), a battle-tested reference implementation.

## Purpose

The validation framework enables:

- **Correctness Verification**: Prove rustybt produces accurate trading simulation results
- **Layer-by-Layer Comparison**: Compare data handling, signals, orders, broker transactions, and portfolio returns
- **Discrepancy Investigation**: Systematically discover and classify differences as bugs or intentional design choices
- **Regression Prevention**: Ensure future changes don't break validated behavior

## Documentation

### User Guides

- [Getting Started](getting-started.md) - Install dependencies and run your first validation session
- [Strategy Implementation Guide](strategy-implementation-guide.md) - Add your own strategies to the validation suite
- [Investigation Workflow Guide](investigation-guide.md) - Investigate and classify discrepancies

### Reference

- [Design Differences](design-differences.md) - Known intentional differences between rustybt and Backtrader
- [Bug Fixes](bug-fixes.md) - Issues discovered through validation and their resolutions
- [Validation Summary](validation-summary.md) - Current validation status across all strategies

## Quick Start

```bash
# Install validation dependencies
pip install -e ".[validation]"

# Create a validation session
rustybt-validate session create sma_crossover \
    --data tests/validation/fixtures/validation_data.parquet

# Run validation
rustybt-validate run <session_id>

# View results
rustybt-validate report <session_id>
```

See the [Getting Started Guide](getting-started.md) for complete instructions.

## Architecture

The validation framework uses a **log-based comparison architecture**:

1. **Dual Implementation**: Each strategy is implemented identically in both rustybt and Backtrader
2. **Structured Logging**: Both implementations log events in a standardized JSONL format
3. **Layer Comparison**: Logs are compared across 5 validation layers (data, signals, orders, broker, portfolio)
4. **Finding Classification**: Discrepancies are classified as BUG (requires fix) or DESIGN (intentional difference)

```
┌─────────────────┐     ┌─────────────────┐
│   rustybt       │     │   Backtrader    │
│   Strategy      │     │   Strategy      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  rustybt.jsonl  │     │ backtrader.jsonl│
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
            ┌─────────────────┐
            │  Comparison     │
            │  Engine         │
            └────────┬────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
         ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Layer 1 │ │ Layer 2 │ │ Layer N │
    │ Data    │ │ Signals │ │ ...     │
    └─────────┘ └─────────┘ └─────────┘
```

## Validated Strategies

The framework validates 4 representative strategies:

| Strategy | Description | Status |
|----------|-------------|--------|
| SMA Crossover | Simple moving average crossover | Validated |
| Mean Reversion | Bollinger band mean reversion | Validated |
| Momentum | Rate of change momentum | Validated |
| Multi-Factor | Combined signal strategy | Validated |

## CLI Commands

```bash
# Session management
rustybt-validate session create <strategy> --data <path>
rustybt-validate session list [--status <status>]
rustybt-validate session show <session_id>
rustybt-validate session resume <session_id>

# Validation execution
rustybt-validate run <session_id>

# Investigation
rustybt-validate investigate <session_id> [--layer <layer>]
rustybt-validate classify <finding_id> --type BUG|DESIGN --rationale "..."

# Reporting
rustybt-validate report <session_id> [--layer <layer>] [--format md|json]
rustybt-validate status  # Overall validation status
```

## Project Structure

```
rustybt/
├── rustybt/validation/           # Validation framework library
│   ├── base_strategy.py          # ValidatedStrategy base classes
│   ├── session.py                # SessionManager
│   ├── comparators.py            # Layer comparison logic
│   ├── models.py                 # Data models
│   ├── reporting.py              # Report generation
│   └── cli.py                    # CLI commands
├── tests/validation/             # Test infrastructure
│   ├── strategies/               # Dual-implemented strategies
│   │   ├── rustybt/              # rustybt implementations
│   │   └── backtrader/           # Backtrader implementations
│   ├── fixtures/                 # Test data
│   └── config/                   # Tolerance configurations
└── validation-sessions/          # Session storage (gitignored)
```
