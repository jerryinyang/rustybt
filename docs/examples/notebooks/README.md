# RustyBT Jupyter Notebooks

This directory contains example Jupyter notebooks demonstrating RustyBT's capabilities for interactive backtesting, analysis, and optimization.

!!! tip "Viewing Notebooks"
    **On this documentation site**: All notebooks are rendered and viewable in the **Notebooks menu** (left sidebar)
    **On GitHub**: Click the links below to view notebooks in the repository
    **Locally**: Download and open in Jupyter Lab/Notebook

## Available Notebooks

All 12 notebooks are now available! 🎉

### ⭐ Recommended Starting Point

**[10_full_workflow.ipynb](10_full_workflow.ipynb)** - Complete end-to-end workflow

Complete workflow demonstrating the entire RustyBT pipeline from data ingestion to optimization.

- Data ingestion → Strategy development → Backtesting → Analysis → Optimization
- All major features demonstrated in one comprehensive example
- Perfect introduction to the framework

---

### 🚀 Quick Start Examples

Fast-track examples to get you backtesting immediately:

**[crypto_backtest_ccxt.ipynb](crypto_backtest_ccxt.ipynb)** - Cryptocurrency backtesting with CCXT

- Multi-exchange data fetching (Binance, Coinbase, Kraken)
- Data validation and quality checks
- Simple moving average crossover strategy
- Performance analysis and visualization

**[equity_backtest_yfinance.ipynb](equity_backtest_yfinance.ipynb)** - Stock backtesting with yfinance

- Stock and ETF data ingestion
- Strategy development and testing
- Performance metrics calculation

---

### 📚 Getting Started Tutorials

Step-by-step tutorials for learning RustyBT fundamentals:

**[01_getting_started.ipynb](01_getting_started.ipynb)** - Your first backtest

- Setup and configuration
- Creating your first strategy
- Running backtests
- Visualizing results

**[02_data_ingestion.ipynb](02_data_ingestion.ipynb)** - Working with data sources

- yfinance (stocks, ETFs)
- CCXT (cryptocurrencies)
- CSV import
- Data quality checks

**[03_strategy_development.ipynb](03_strategy_development.ipynb)** - Building trading strategies

- Moving average crossover
- Mean reversion strategies
- Momentum strategies

---

### 📊 Analysis & Optimization

Advanced techniques for strategy evaluation and improvement:

**[04_performance_analysis.ipynb](04_performance_analysis.ipynb)** - Performance metrics deep dive

- Interactive visualizations with Plotly
- Key metrics calculation
- Risk-adjusted returns

**[05_optimization.ipynb](05_optimization.ipynb)** - Parameter optimization

- Grid search optimization
- Bayesian optimization
- Finding optimal parameters
- Avoiding overfitting

**[06_walk_forward.ipynb](06_walk_forward.ipynb)** - Walk-forward validation

- Robust validation techniques
- Out-of-sample testing
- Performance degradation analysis

**[07_risk_analytics.ipynb](07_risk_analytics.ipynb)** - Risk metrics and analysis

- Value at Risk (VaR) calculations
- Conditional VaR (CVaR)
- Beta analysis
- Drawdown analysis

**[08_portfolio_construction.ipynb](08_portfolio_construction.ipynb)** - Multi-asset portfolios

- Equal-weight portfolios
- Risk-parity allocation
- Rebalancing logic

**[09_live_paper_trading.ipynb](09_live_paper_trading.ipynb)** - Paper trading setup

- Real-time testing
- Paper broker configuration
- Live monitoring

---

## Features Demonstrated

All notebooks showcase:
- ✅ **Interactive Visualizations** using Plotly (equity curves, drawdowns, distributions)
- ✅ **DataFrame Exports** to both pandas and polars formats
- ✅ **Progress Bars** for long-running operations using tqdm
- ✅ **Async/Await Support** for backtests in notebooks
- ✅ **Rich Display** with `_repr_html_()` methods for strategy objects

## Setup

### Install Dependencies
```bash
# Install RustyBT with notebook support
pip install rustybt plotly tqdm ipywidgets nest-asyncio

# Or using uv (recommended)
uv pip install rustybt plotly tqdm ipywidgets nest-asyncio
```

### Launch Jupyter
```bash
jupyter lab
```

### Initialize Notebook Environment
```python
from rustybt.analytics import setup_notebook
setup_notebook()
```

## Usage Patterns

### Basic Backtest
```python
from rustybt import TradingAlgorithm
from rustybt.analytics import plot_equity_curve

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')

    def handle_data(self, context, data):
        self.order(context.asset, 100)

algo = MyStrategy(...)
results = algo.run()

# Visualize
fig = plot_equity_curve(results)
fig.show()
```

### Async Backtest with Progress
```python
from rustybt.analytics import async_backtest, setup_notebook

setup_notebook()

# Run async
results = await async_backtest(algo, show_progress=True)
```

### Export to DataFrame
```python
# Export results to polars
results_pl = algo.to_polars(results)

# Export positions
positions = algo.get_positions_df()

# Export transactions
transactions = algo.get_transactions_df()
```

### Visualizations
```python
from rustybt.analytics import (
    plot_equity_curve,
    plot_drawdown,
    plot_returns_distribution,
    plot_rolling_metrics
)

# Equity curve with drawdown
plot_equity_curve(results, show_drawdown=True).show()

# Returns distribution
plot_returns_distribution(results).show()

# Rolling metrics (Sharpe, volatility)
plot_rolling_metrics(results, window=60).show()
```

## Tips for Notebook Development

1. **Always call `setup_notebook()`** at the beginning to configure async support
2. **Use progress bars** for operations that take >5 seconds
3. **Export DataFrames** for custom analysis with pandas/polars
4. **Save figures** for reports:
   ```python
   fig.write_html("equity_curve.html")
   fig.write_image("equity_curve.png")
   ```
5. **Use dark theme** for better visibility: `plot_equity_curve(results, theme='dark')`

## Contributing

To add new example notebooks:
1. Follow the naming convention: `NN_topic_name.ipynb`
2. Include markdown cells explaining each step
3. Demonstrate at least 3 analytics features
4. Add expected runtime in the first cell
5. Ensure notebook runs without errors using `jupyter nbconvert --execute`

## Support

For issues or questions:
- Documentation: https://rustybt.readthedocs.io
- GitHub Issues: https://github.com/rustybt/rustybt/issues
- Discussions: https://github.com/rustybt/rustybt/discussions
