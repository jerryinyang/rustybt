# RustyBT Jupyter Notebooks

This directory contains example Jupyter notebooks demonstrating RustyBT's capabilities for interactive backtesting, analysis, and optimization.

## Available Notebooks

All 13 notebooks are now available! 🎉

### Core Examples
1. **crypto_backtest_ccxt.ipynb** - Cryptocurrency backtesting using CCXT adapter
   - Multi-exchange data fetching (Binance, Coinbase, Kraken)
   - Data validation and quality checks
   - Simple moving average crossover strategy
   - Performance analysis and visualization

2. **equity_backtest_yfinance.ipynb** - Equity backtesting using yfinance
   - Stock and ETF data ingestion
   - Strategy development and testing
   - Performance metrics calculation

### Getting Started
3. **01_getting_started.ipynb** - Simple backtest walkthrough
   - Setup and configuration
   - Creating your first strategy
   - Running backtests
   - Visualizing results

4. **02_data_ingestion.ipynb** - Data ingestion from multiple sources
   - yfinance (stocks, ETFs)
   - CCXT (cryptocurrencies)
   - CSV import
   - Data quality checks

5. **03_strategy_development.ipynb** - Building custom strategies
   - Moving average crossover
   - Mean reversion
   - Momentum strategies

### Analysis & Optimization
6. **04_performance_analysis.ipynb** - Deep dive into performance metrics
   - Interactive visualizations
   - Key metrics calculation
   - Risk-adjusted returns

7. **05_optimization.ipynb** - Grid search and Bayesian optimization
   - Parameter tuning
   - Finding optimal parameters
   - Avoiding overfitting

8. **06_walk_forward.ipynb** - Walk-forward optimization
   - Robust validation
   - Out-of-sample testing
   - Performance degradation analysis

9. **07_risk_analytics.ipynb** - VaR, CVaR, and beta analysis
   - Value at Risk calculations
   - Risk metrics
   - Drawdown analysis

10. **08_portfolio_construction.ipynb** - Multi-asset portfolio strategies
    - Equal-weight portfolios
    - Risk-parity allocation
    - Rebalancing logic

11. **09_live_paper_trading.ipynb** - Paper trading setup and execution
    - Real-time testing
    - Paper broker setup
    - Live monitoring

### Complete Workflow
12. **10_full_workflow.ipynb** ⭐ **RECOMMENDED START** - Complete workflow from data to optimization
    - Data ingestion → Strategy → Backtest → Analysis → Optimization
    - Complete end-to-end example
    - All features demonstrated

13. **11_advanced_topics.ipynb** - Custom indicators and multi-asset strategies
    - Building custom indicators
    - Advanced techniques
    - Multi-asset correlation

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
