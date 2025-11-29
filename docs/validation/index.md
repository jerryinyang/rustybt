# Validation Framework Documentation

Welcome to the rustybt Validation Framework documentation. This framework validates rustybt's trading behavior against Backtrader to ensure behavioral equivalence across 5 layers of trading logic.

---

## Quick Links

| Task | Documentation |
|------|---------------|
| **Get started with validation** | [Getting Started Guide](getting-started.md) |
| **Add a new strategy for validation** | [Strategy Implementation Guide](strategy-implementation-guide.md) |
| **Investigate and classify findings** | [Investigation Workflow Guide](investigation-guide.md) |
| **Run validation commands** | [CLI Reference](cli-reference.md) |
| **Use the Python API** | [Python API Reference](python-api-reference.md) |
| **Troubleshoot issues** | [Troubleshooting Guide](troubleshooting.md) |
| **Copy-paste recipes** | [Examples & Recipes Cookbook](cookbook.md) |

---

## User Journey Paths

### New User Path

If you're new to the validation framework, follow this path:

```
┌─────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
│  1. Getting     │───▶│  2. Troubleshoot   │───▶│  3. Learn           │
│     Started     │    │     Common Issues  │    │     CLI Commands    │
└─────────────────┘    └────────────────────┘    └─────────────────────┘
```

1. **[Getting Started](getting-started.md)** - Install the framework, run your first validation session, and understand the 5-layer comparison model
2. **[Troubleshooting](troubleshooting.md)** - Resolve common setup and execution issues
3. **[CLI Reference](cli-reference.md)** - Learn the command-line interface for daily use

### Experienced User Path

For users adding new strategies or performing deep investigations:

```
┌─────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
│  1. Strategy    │───▶│  2. Investigation  │───▶│  3. Advanced        │
│     Guide       │    │     Workflow       │    │     Recipes         │
└─────────────────┘    └────────────────────┘    └─────────────────────┘
```

1. **[Strategy Implementation Guide](strategy-implementation-guide.md)** - Implement strategies in both frameworks for comparison
2. **[Investigation Workflow Guide](investigation-guide.md)** - Systematically investigate and classify findings
3. **[Cookbook](cookbook.md)** - Advanced recipes for CI/CD, version comparison, and custom tolerances

### Contributor Path

For developers contributing to the validation framework:

```
┌─────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
│  1. Python API  │───▶│  2. Validation     │───▶│  3. rustybt         │
│     Reference   │    │     Results        │    │     Contributing    │
└─────────────────┘    └────────────────────┘    └─────────────────────┘
```

1. **[Python API Reference](python-api-reference.md)** - Understand the framework's programmatic interfaces
2. **[Validation Results](validation-summary.md)** - Review current validation status and findings
3. **[rustybt Contributing Guide](../CONTRIBUTING.md)** - Guidelines for contributing to the project

---

## Documentation Index

### Guides

| Document | Description | Audience |
|----------|-------------|----------|
| [Getting Started](getting-started.md) | Installation, first session, 5-layer model overview | New users |
| [Strategy Implementation Guide](strategy-implementation-guide.md) | Creating strategies for both frameworks, logging requirements | Strategy developers |
| [Investigation Workflow Guide](investigation-guide.md) | Finding discrepancies, classifying as BUG vs DESIGN, verification | Validators |

### Reference

| Document | Description | Audience |
|----------|-------------|----------|
| [CLI Reference](cli-reference.md) | Complete command documentation with examples | All users |
| [Python API Reference](python-api-reference.md) | Classes, methods, and programmatic usage | Developers |
| [Troubleshooting](troubleshooting.md) | Error messages, common issues, resolutions | All users |
| [Cookbook](cookbook.md) | Copy-paste recipes for common tasks | All users |

### Validation Results

| Document | Description | Audience |
|----------|-------------|----------|
| [Validation Summary](validation-summary.md) | Overall validation status and progress | Stakeholders |
| [Design Differences](design-differences.md) | Documented intentional differences between frameworks | Developers |
| [Bug Fixes](bug-fixes.md) | Bugs identified and fixed through validation | Developers |

---

## The 5-Layer Validation Model

The validation framework compares rustybt and Backtrader across 5 layers:

| Layer | Name | What's Compared |
|-------|------|-----------------|
| **1** | Data Handling | Bar data, timestamps, OHLCV values, lookahead bias detection |
| **2** | Signal Computation | Indicator values, signal timing, calculation accuracy |
| **3** | Order Lifecycle | Order creation, modification, cancellation, fill events |
| **4** | Broker Transaction | Commissions, slippage, partial fills, cash management |
| **5** | Portfolio Returns | Portfolio values, returns, metrics (Sharpe, drawdown) |

Each layer builds on the previous ones. Data accuracy affects signals, signals affect orders, orders affect transactions, and transactions affect portfolio returns.

---

## Finding Classification

Discrepancies between frameworks are classified as:

| Classification | Description | Action |
|----------------|-------------|--------|
| **BUG** | Incorrect behavior in rustybt that needs fixing | Fix the bug, re-validate |
| **DESIGN** | Intentional difference between frameworks | Document and accept |

All findings must be classified before validation is complete. Unclassified findings are tracked as pending.

---

## Validation Workflow Overview

```
┌──────────┐    ┌───────────┐    ┌────────────┐    ┌───────────────┐    ┌────────────┐    ┌───────────┐
│ CREATED  │───▶│ EXECUTION │───▶│ COMPARISON │───▶│ INVESTIGATION │───▶│ VERIFICATION│───▶│ COMPLETED │
└──────────┘    └───────────┘    └────────────┘    └───────────────┘    └────────────┘    └───────────┘
     │               │                │                   │                   │                │
     │               │                │                   │                   │                │
   Create         Run both        Compare logs      Classify all        Verify fixes      All findings
   session        strategies      5 layers          discrepancies       are applied       resolved
```

**Sessions** track the validation state through each stage. Sessions can be resumed if interrupted.

---

## Common Tasks

### Validate a Strategy

```bash
# Create session
rustybt-validate session create my_strategy

# Run strategies
rustybt-validate run my_strategy

# Compare results
rustybt-validate compare <session_id>

# Investigate findings
rustybt-validate investigate <session_id>

# Verify all findings classified
rustybt-validate verify <session_id>

# Generate report
rustybt-validate report <session_id>
```

### Check Validation Status

```bash
# List all sessions
rustybt-validate session list

# View session details
rustybt-validate session show <session_id>

# Check overall progress
rustybt-validate progress
```

### Troubleshoot Issues

```bash
# Validate log file
rustybt-validate log validate <log_file>

# Check configuration
rustybt-validate config show

# View session findings
rustybt-validate session findings <session_id>
```

---

## Related Documentation

### rustybt Framework Documentation

| Document | Description |
|----------|-------------|
| [rustybt User Guide](../user-guide/index.md) | Main framework documentation |
| [rustybt API Reference](../api/index.md) | Framework API documentation |
| [Examples](../examples/index.md) | Strategy examples and tutorials |

### Internal Documentation

These documents are for framework maintainers and contributors:

| Document | Description |
|----------|-------------|
| [Architecture](../internal/architecture.md) | System design and component structure |
| [PRD](../internal/prd.md) | Product requirements document |
| [Sprint Artifacts](../internal/sprint-artifacts/) | Story files and sprint status |

---

## Documentation Structure

```
docs/validation/
├── index.md                        # This file - main entry point
│
├── Guides/
│   ├── getting-started.md          # Installation and first session
│   ├── strategy-implementation-guide.md  # Creating strategies
│   └── investigation-guide.md      # Investigating findings
│
├── Reference/
│   ├── cli-reference.md            # CLI commands
│   ├── python-api-reference.md     # Python API
│   ├── troubleshooting.md          # Issue resolution
│   └── cookbook.md                 # Recipes and examples
│
└── Results/
    ├── validation-summary.md       # Overall status
    ├── design-differences.md       # Documented differences
    └── bug-fixes.md                # Fixed bugs
```

---

## Keyboard Shortcuts & Tips

### CLI Shortcuts

| Shortcut | Full Command | Description |
|----------|--------------|-------------|
| `session list` | Full output | List all sessions |
| `session list -q` | Quiet mode | Session IDs only |
| `session show <id>` | Full details | Session state and progress |
| `progress` | Dashboard | Overall validation progress |

### Investigation Tips

1. **Start with Layer 1** - Data issues cascade to all other layers
2. **Batch similar findings** - Classify patterns together
3. **Document DESIGN differences** - Future validators will thank you
4. **Use `--verbose`** - Get detailed output when debugging

### Report Tips

1. **JSON for CI/CD** - Machine-readable for automation
2. **Markdown for stakeholders** - Human-readable summaries
3. **Layer-specific reports** - Deep-dive into problem areas

---

## Getting Help

- **[Troubleshooting Guide](troubleshooting.md)** - Common issues and solutions
- **[GitHub Issues](https://github.com/rustybt/rustybt/issues)** - Report bugs or request features
- **[CLI Help](cli-reference.md#getting-help)** - `rustybt-validate --help`

---

## Document Information

| Field | Value |
|-------|-------|
| Last Updated | 2024-11-24 |
| Validation Framework Version | 1.0.0 |
| Status | Complete |

---

*Navigation: [Getting Started](getting-started.md) | [CLI Reference](cli-reference.md) | [Python API](python-api-reference.md) | [Troubleshooting](troubleshooting.md)*
