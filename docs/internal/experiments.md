# Experiments and Validation Tests

RustyBT includes a collection of experiments and validation tests to ensure correctness and identify implementation differences compared to other backtesting frameworks.

## Location

All experiments are located in the `/experiments` directory at the project root.

## Directory Structure

```
experiments/
├── README.md                           # Overview of all experiments
└── backtrader_comparison/              # Backtrader validation
    ├── README.md                       # Detailed documentation
    ├── test_sma_crossover_comparison.py
    ├── test_mag7_portfolio_comparison.py
    ├── analyze_trade_differences.py
    ├── analyze_root_cause.py
    └── TRADE_DIFFERENCE_FINDINGS.md
```

## Current Experiments

### Backtrader Comparison (October 2025)

Comprehensive validation of RustyBT against Backtrader using SMA 20/50 crossover strategies.

**Scope:**
- Single stock test (AAPL, 2000-2020)
- Portfolio test (MAG7 stocks, 2015-2023)
- Trade-by-trade comparison
- Root cause analysis of differences

**Key Results:**
- 96.9% trade matching rate
- Identified 3 main sources of differences:
  1. Position sizing methodology (compounding vs fixed)
  2. Exit signal detection (10 missing signals)
  3. Edge case handling (low prices, high volatility)
- Financial impact: 55% portfolio value difference

**Location:** [`experiments/backtrader_comparison/`](../experiments/backtrader_comparison/)

**Documentation:** See [`TRADE_DIFFERENCE_FINDINGS.md`](../experiments/backtrader_comparison/TRADE_DIFFERENCE_FINDINGS.md)

## Running Experiments

Navigate to the specific experiment directory and follow the README instructions:

```bash
cd experiments/backtrader_comparison/
python3 test_sma_crossover_comparison.py
```

## Adding New Experiments

To add a new experiment:

1. Create a subdirectory: `experiments/your_experiment/`
2. Add a README.md with:
   - Purpose and hypothesis
   - Setup instructions
   - How to run
   - Expected results
3. Implement experiment scripts
4. Document findings
5. Update `experiments/README.md`

## Guidelines

- Keep experiments self-contained
- Document all dependencies
- Include analysis scripts with tests
- Don't commit large data files
- Document findings in markdown

## Integration with Main Codebase

Experiments are:
- **NOT** part of the main test suite
- **NOT** included in package distribution
- **NOT** subject to same code standards
- **Useful** for validation and research

Use experiments to:
- Validate correctness against other frameworks
- Test new features before integration
- Benchmark performance
- Research implementation approaches

## See Also

- [Testing Guide](testing.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Development Setup](development.md)

---

For questions about experiments, see the README in each experiment directory or open an issue on GitHub.
