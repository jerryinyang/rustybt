# Advanced RustyBT Tutorial Notebooks

This directory contains advanced tutorial notebooks covering complex strategies, optimization techniques, and professional trading workflows.

## Available Notebooks

### 11. Pipeline API Deep Dive
**[11_pipeline_deep_dive.ipynb](11_pipeline_deep_dive.ipynb)**

Comprehensive guide to RustyBT's Pipeline API for factor-based strategies:
- **Factors** - Technical indicators, custom computations
- **Filters** - Dynamic universe selection
- **Classifiers** - Categorical asset grouping
- **Custom Terms** - Building proprietary indicators
- **Production Strategies** - Combining multiple factors

**Prerequisites:** Basic Python, understanding of technical indicators
**Runtime:** ~5 minutes

### 12. Advanced Order Management
**[12_advanced_order_management.ipynb](12_advanced_order_management.ipynb)**

Professional order management techniques:
- **Bracket Orders** - Automatic stop loss + take profit
- **OCO Orders** - One-Cancels-Other pairs for breakouts
- **Trailing Stops** - Dynamic stop losses
- **Order Tracking** - Managing order lifecycle
- **Partial Fills** - Handling incomplete executions
- **Position Scaling** - Pyramiding in/out of positions

**Prerequisites:** Understanding of order types
**Runtime:** ~7 minutes

### 13. Portfolio Optimization + Walk-Forward Analysis
**[13_portfolio_optimization_walk_forward.ipynb](13_portfolio_optimization_walk_forward.ipynb)**

Combining portfolio allocation with walk-forward validation:
- **Sub-Strategy Definition** - Multiple uncorrelated strategies
- **Individual Optimization** - Walk-forward per strategy
- **Portfolio Allocation** - Fixed and dynamic allocation
- **Allocation Optimization** - Walk-forward optimize weights
- **Risk Parity** - Volatility-based allocation
- **Kelly Criterion** - Growth-optimal allocation
- **Performance Analysis** - In-sample vs out-of-sample metrics

**Prerequisites:** Notebooks 05 (Optimization), 06 (Walk-Forward), 08 (Portfolio)
**Runtime:** ~15 minutes

### 14. Multi-Timeframe Strategies
**[14_multi_timeframe_strategies.ipynb](14_multi_timeframe_strategies.ipynb)**

Trading across multiple timeframes for better context:
- **Timeframe Hierarchy** - Higher for trend, lower for entries
- **Three-Timeframe Alignment** - Weekly + Daily + Hourly
- **Adaptive Timeframes** - Switch based on volatility
- **Higher TF Stops** - Use daily structure for stop placement
- **Timeframe Combinations** - Best practices for different styles

**Prerequisites:** Understanding of technical analysis across timeframes
**Runtime:** ~8 minutes

---

## Recommended Learning Path

### Path 1: Factor-Based Strategies
1. Start with basic notebooks (01-04)
2. **Notebook 11: Pipeline Deep Dive**
3. **Notebook 13: Portfolio Optimization + Walk-Forward**
4. Combine with live trading (09)

### Path 2: Discretionary/Technical Trading
1. Start with basic notebooks (01-04)
2. **Notebook 12: Advanced Order Management**
3. **Notebook 14: Multi-Timeframe Strategies**
4. Apply to live trading (09)

### Path 3: Systematic Portfolio Management
1. Complete basic series (01-10)
2. **Notebook 11: Pipeline Deep Dive** (for sub-strategies)
3. **Notebook 13: Portfolio Optimization + Walk-Forward**
4. Deploy with live portfolio allocator

---

## Advanced Topics Covered

### Quantitative Research
- Cross-sectional factor analysis
- Custom factor development
- Factor combination and weighting
- Universe selection and screening

### Risk Management
- Bracket orders for automated stops
- Trailing stops for profit protection
- Position sizing and scaling
- Portfolio-level risk parity

### Optimization
- Walk-forward analysis
- Parameter robustness testing
- Portfolio weight optimization
- Adaptive allocation

### Execution
- Order type selection
- Partial fill handling
- Order modification
- Multi-asset order aggregation

### Market Analysis
- Multi-timeframe trend identification
- Timeframe alignment strategies
- Volatility regime detection
- Adaptive strategy selection

---

## Prerequisites

### Knowledge Requirements
- **Programming:** Python (intermediate), pandas, numpy
- **Trading:** Order types, position management, risk management
- **Statistics:** Basic statistics, correlation, optimization concepts
- **Finance:** Portfolio theory, risk metrics (Sharpe, Sortino, etc.)

### System Requirements
- **Memory:** 8GB+ recommended for optimization notebooks
- **CPU:** Multi-core recommended for parallel optimization
- **Data:** Access to bundle data (yfinance, CCXT, etc.)

---

## Tips for Success

### 1. Start Simple
Don't try to combine everything at once. Master each technique individually before combining.

### 2. Backtest Thoroughly
Always backtest advanced strategies across multiple market conditions:
- Bull markets
- Bear markets
- Sideways/choppy markets
- High volatility periods
- Low volatility periods

### 3. Paper Trade First
Before live trading with advanced techniques:
1. Backtest with realistic transaction costs
2. Paper trade for at least 1-3 months
3. Verify order handling works as expected
4. Monitor for any edge cases

### 4. Monitor Performance
Track these metrics regularly:
- In-sample vs out-of-sample performance
- Parameter stability over time
- Strategy correlation changes
- Execution quality (slippage, fills)

### 5. Risk Management is Paramount
- **Always use stops** - Especially with advanced position sizing
- **Limit position sizes** - Don't over-leverage
- **Diversify strategies** - Don't rely on one approach
- **Monitor drawdowns** - Have circuit breakers in place

---

## Common Pitfalls

### ❌ Over-optimization
**Problem:** Curve-fitting parameters to historical data
**Solution:** Use walk-forward analysis, out-of-sample testing, and simple parameter spaces

### ❌ Ignoring Transaction Costs
**Problem:** Strategies look great in backtest but fail live
**Solution:** Include realistic slippage and commission models

### ❌ Over-complicating Strategies
**Problem:** Too many parameters, conditions, and timeframes
**Solution:** Keep strategies simple; complexity ≠ profitability

### ❌ Insufficient Testing
**Problem:** Moving to live trading too quickly
**Solution:** Test across multiple years, market conditions, and assets

### ❌ Poor Risk Management
**Problem:** Large drawdowns due to lack of stops or over-leveraging
**Solution:** Always use stops, limit leverage, and size positions appropriately

---

## Getting Help

### Documentation
- [RustyBT Documentation](https://rustybt.readthedocs.io/)
- [API Reference](https://rustybt.readthedocs.io/en/latest/api/)
- [Pipeline Guide](https://rustybt.readthedocs.io/en/latest/pipeline/)
- [Optimization Guide](https://rustybt.readthedocs.io/en/latest/optimization/)

### Community
- [GitHub Discussions](https://github.com/rustybt/rustybt/discussions)
- [GitHub Issues](https://github.com/rustybt/rustybt/issues)

### Support
- Check existing issues before creating new ones
- Provide minimal reproducible examples
- Include error messages and environment details

---

## Contributing

Have an idea for a new advanced notebook? We'd love to see it!

**Guidelines:**
1. Focus on a single advanced topic
2. Include clear explanations and examples
3. Demonstrate with working code
4. Add to this README with proper description
5. Ensure notebook runs without errors
6. Include expected runtime

**Potential Topics:**
- Custom data feed integration
- Machine learning factor generation
- Options strategies
- Futures term structure
- Statistical arbitrage
- Market microstructure analysis
- Risk parity with constraints
- Bayesian portfolio optimization

---

## License

These notebooks are part of the RustyBT project and are available under the same license terms.
