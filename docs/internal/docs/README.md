# Examples & Tutorials

Welcome to the RustyBT examples and tutorials! This section contains practical, runnable code demonstrating various features of the framework.

## Quick Start

All examples are available in the [`examples/`](https://github.com/jerryinyang/rustybt/tree/main/examples) directory of the repository:

```bash
# Clone the repository
git clone https://github.com/jerryinyang/rustybt.git
cd rustybt

# Install with examples dependencies
uv sync --all-extras

# Run an example
python examples/backtest_with_cache.py
```

## 📚 Interactive Tutorials (Jupyter Notebooks)

Step-by-step walkthroughs perfect for learning:

1. [**Getting Started**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/01_getting_started.ipynb) - Your first backtest
2. [**Data Ingestion**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/02_data_ingestion.ipynb) - Import data from various sources
3. [**Strategy Development**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/03_strategy_development.ipynb) - Build trading strategies
4. [**Performance Analysis**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/04_performance_analysis.ipynb) - Analyze backtest results
5. [**Strategy Optimization**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/05_optimization.ipynb) - Parameter tuning
6. [**Walk-Forward Analysis**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/06_walk_forward.ipynb) - Out-of-sample testing
7. [**Risk Analytics**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/07_risk_analytics.ipynb) - Risk metrics and analysis
8. [**Portfolio Construction**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/08_portfolio_construction.ipynb) - Multi-strategy portfolios
9. [**Paper Trading**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/09_live_paper_trading.ipynb) - Live trading simulation
10. [**Full Workflow**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/10_full_workflow.ipynb) - Complete workflow example
11. [**Advanced Topics**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/11_advanced_topics.ipynb) - Advanced features
12. [**Crypto Backtest**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/crypto_backtest_ccxt.ipynb) - Cryptocurrency trading
13. [**Equity Backtest**](https://github.com/jerryinyang/rustybt/blob/main/examples/notebooks/equity_backtest_yfinance.ipynb) - Stock market trading

## 📂 Example Categories

### Data Ingestion

- [**ingest_yfinance.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/ingest_yfinance.py) - Import data from Yahoo Finance
- [**ingest_ccxt.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/ingest_ccxt.py) - Import cryptocurrency data via CCXT
- [**custom_data_adapter.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/custom_data_adapter.py) - Build custom data adapters

### Basic Backtesting

- [**backtest_with_cache.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/backtest_with_cache.py) - Use intelligent caching
- [**cache_warming.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/cache_warming.py) - Pre-warm data cache for faster backtests

### Live Trading

- [**live_trading_simple.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/live_trading_simple.py) - Simple live trading setup
- [**live_trading.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/live_trading.py) - Full live trading example
- [**custom_broker_adapter.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/custom_broker_adapter.py) - Build custom broker integrations

### Advanced Features

- [**allocation_algorithms_tutorial.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/allocation_algorithms_tutorial.py) - Portfolio allocation strategies
- [**slippage_models_tutorial.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/slippage_models_tutorial.py) - Transaction cost modeling
- [**latency_simulation_tutorial.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/latency_simulation_tutorial.py) - Realistic latency simulation
- [**borrow_cost_tutorial.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/borrow_cost_tutorial.py) - Short selling borrow costs
- [**overnight_financing_tutorial.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/overnight_financing_tutorial.py) - Leveraged position financing

### Strategy Optimization

- [**grid_search_ma_crossover.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/optimization/grid_search_ma_crossover.py) - Grid search optimization
- [**random_search_vs_grid.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/optimization/random_search_vs_grid.py) - Random search comparison
- [**bayesian_optimization_5param.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/optimization/bayesian_optimization_5param.py) - Bayesian optimization
- [**genetic_algorithm_nonsmooth.ipynb**](https://github.com/jerryinyang/rustybt/blob/main/examples/optimization/genetic_algorithm_nonsmooth.ipynb) - Genetic algorithm notebook
- [**parallel_optimization_example.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/optimization/parallel_optimization_example.py) - Parallel optimization
- [**walk_forward_analysis.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/optimization/walk_forward_analysis.py) - Walk-forward optimization
- [**sensitivity_analysis.ipynb**](https://github.com/jerryinyang/rustybt/blob/main/examples/optimization/sensitivity_analysis.ipynb) - Parameter sensitivity analysis
- [**noise_infusion_robustness.ipynb**](https://github.com/jerryinyang/rustybt/blob/main/examples/optimization/noise_infusion_robustness.ipynb) - Robustness testing

### Analytics & Reporting

- [**generate_backtest_report.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/generate_backtest_report.py) - Generate PDF/HTML reports
- [**attribution_analysis_example.py**](https://github.com/jerryinyang/rustybt/blob/main/examples/attribution_analysis_example.py) - Performance attribution

## 💻 Running Examples Locally

### Using uv (Recommended)

```bash
# Install RustyBT with all dependencies
uv sync --all-extras

# Run any example
python examples/backtest_with_cache.py

# Run Jupyter notebooks
jupyter lab examples/notebooks/
```

### Using pip

```bash
# Create and activate virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install with all extras
pip install -e ".[dev,test,optimization]"

# Run examples
python examples/backtest_with_cache.py
```

## 📖 Learning Path

We recommend following this path for learning RustyBT:

### 1. **Beginner** - Basic Backtesting
- Start with `01_getting_started.ipynb`
- Follow `02_data_ingestion.ipynb`
- Try `backtest_with_cache.py`
- Review `03_strategy_development.ipynb`

### 2. **Intermediate** - Optimization & Analysis
- Learn optimization with `05_optimization.ipynb`
- Explore `grid_search_ma_crossover.py`
- Understand walk-forward with `06_walk_forward.ipynb`
- Analyze with `04_performance_analysis.ipynb`

### 3. **Advanced** - Portfolio & Live Trading
- Multi-strategy with `08_portfolio_construction.ipynb`
- Transaction costs with `slippage_models_tutorial.py`
- Paper trading with `09_live_paper_trading.ipynb`
- Go live with `live_trading_simple.py`

### 4. **Expert** - Custom Extensions
- Custom data with `custom_data_adapter.py`
- Custom broker with `custom_broker_adapter.py`
- Advanced features in `11_advanced_topics.ipynb`

## 🔗 Additional Resources

- [User Guides](../guides/decimal-precision-configuration.md) - Detailed feature guides
- [API Reference](../api/order-types.md) - Complete API documentation
- [GitHub Repository](https://github.com/jerryinyang/rustybt) - View source code
- [GitHub Issues](https://github.com/jerryinyang/rustybt/issues) - Report bugs or request features

## 🤝 Contributing Examples

Have a useful example to share? We welcome contributions!

1. Fork the repository
2. Add your example to `examples/` or `examples/notebooks/`
3. Update the README
4. Submit a pull request

See our [Contributing Guide](../about/contributing.md) for more details.
