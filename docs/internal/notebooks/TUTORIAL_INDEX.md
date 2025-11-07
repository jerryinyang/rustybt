# RustyBT Tutorial Notebooks - Complete Index

## 🎯 Quick Navigation

**New to RustyBT?** Start with [10_full_workflow.ipynb](10_full_workflow.ipynb) for a complete end-to-end example.

**Looking for specific features?** Use the categorized index below.

---

## 📚 Learning Paths

### Path 1: Complete Beginner (0-2 hours)
Perfect if you're new to algorithmic trading or RustyBT.

1. **[01_getting_started.ipynb](01_getting_started.ipynb)** (3 min)
   - Your first backtest
   - Basic strategy structure
   - Running and visualizing results

2. **[02_data_ingestion.ipynb](02_data_ingestion.ipynb)** (5 min)
   - yfinance (stocks, ETFs)
   - CCXT (cryptocurrencies)
   - CSV import

3. **[03_strategy_development.ipynb](03_strategy_development.ipynb)** (8 min)
   - Moving average crossover
   - Mean reversion
   - Momentum strategies

4. **[10_full_workflow.ipynb](10_full_workflow.ipynb)** (15 min)
   - **⭐ RECOMMENDED START**
   - Complete pipeline: data → strategy → backtest → optimization

### Path 2: Strategy Optimization (2-4 hours)
Learn to optimize and validate your strategies.

1. **[04_performance_analysis.ipynb](04_performance_analysis.ipynb)** (5 min)
   - Performance metrics deep dive
   - Interactive visualizations
   - Risk-adjusted returns

2. **[05_optimization.ipynb](05_optimization.ipynb)** (8 min)
   - Grid search
   - Bayesian optimization
   - Avoiding overfitting

3. **[06_walk_forward.ipynb](06_walk_forward.ipynb)** (10 min)
   - Walk-forward validation
   - Out-of-sample testing
   - Performance degradation analysis

4. **[15_monte_carlo_basics.ipynb](15_monte_carlo_basics.ipynb)** (8 min) 🆕
   - Monte Carlo simulation
   - Data permutation
   - Noise infusion
   - Confidence intervals

5. **[16_sensitivity_analysis_basics.ipynb](16_sensitivity_analysis_basics.ipynb)** (6 min) 🆕
   - Parameter stability analysis
   - 1D and 2D sensitivity plots
   - Identifying stable regions

### Path 3: Advanced Techniques (4-6 hours)
Master advanced features and combine multiple techniques.

1. **[11_pipeline_deep_dive.ipynb](11_pipeline_deep_dive.ipynb)** (15 min)
   - Factors, Filters, Classifiers
   - Custom pipeline terms
   - Cross-sectional analysis

2. **[07_risk_analytics.ipynb](07_risk_analytics.ipynb)** (8 min)
   - VaR and CVaR
   - Beta analysis
   - Drawdown metrics

3. **[08_portfolio_construction.ipynb](08_portfolio_construction.ipynb)** (10 min)
   - Multi-asset portfolios
   - Risk-parity allocation
   - Rebalancing strategies

4. **[12_advanced_order_management.ipynb](12_advanced_order_management.ipynb)** (12 min)
   - Complex order types
   - Slippage and commission models
   - Order execution simulation

5. **[13_portfolio_optimization_walk_forward.ipynb](13_portfolio_optimization_walk_forward.ipynb)** (15 min)
   - Portfolio allocation optimization
   - Dynamic allocation methods
   - Walk-forward portfolio optimization

6. **[14_multi_timeframe_strategies.ipynb](14_multi_timeframe_strategies.ipynb)** (12 min)
   - Multiple timeframe analysis
   - Combining signals across timeframes

### Path 4: Production & Live Trading (2-3 hours)
Prepare strategies for live deployment.

1. **[09_live_paper_trading.ipynb](09_live_paper_trading.ipynb)** (10 min)
   - Paper trading setup
   - Real-time testing
   - Live monitoring

2. **[report_generation.ipynb](report_generation.ipynb)** (8 min)
   - Professional reporting
   - Export formats
   - Custom report templates

---

## 📂 By Module/Feature

### Data Ingestion & Management
- **[02_data_ingestion.ipynb](02_data_ingestion.ipynb)** - Multiple data sources
- **[equity_backtest_yfinance.ipynb](equity_backtest_yfinance.ipynb)** - Stock data with yfinance
- **[crypto_backtest_ccxt.ipynb](crypto_backtest_ccxt.ipynb)** - Crypto data with CCXT

### Strategy Development
- **[03_strategy_development.ipynb](03_strategy_development.ipynb)** - Basic strategies
- **[11_pipeline_deep_dive.ipynb](11_pipeline_deep_dive.ipynb)** - Factor-based strategies
- **[14_multi_timeframe_strategies.ipynb](14_multi_timeframe_strategies.ipynb)** - Multi-timeframe

### Parameter Optimization
- **[05_optimization.ipynb](05_optimization.ipynb)** - Grid search & Bayesian optimization
- **[16_sensitivity_analysis_basics.ipynb](16_sensitivity_analysis_basics.ipynb)** 🆕 - Parameter stability

### Validation & Robustness Testing
- **[06_walk_forward.ipynb](06_walk_forward.ipynb)** - Walk-forward validation
- **[15_monte_carlo_basics.ipynb](15_monte_carlo_basics.ipynb)** 🆕 - Monte Carlo simulation
- **[16_sensitivity_analysis_basics.ipynb](16_sensitivity_analysis_basics.ipynb)** 🆕 - Sensitivity analysis

### Portfolio Management
- **[08_portfolio_construction.ipynb](08_portfolio_construction.ipynb)** - Portfolio basics
- **[13_portfolio_optimization_walk_forward.ipynb](13_portfolio_optimization_walk_forward.ipynb)** - Portfolio optimization

### Risk Management
- **[07_risk_analytics.ipynb](07_risk_analytics.ipynb)** - Risk metrics
- **[12_advanced_order_management.ipynb](12_advanced_order_management.ipynb)** - Order execution

### Performance Analysis
- **[04_performance_analysis.ipynb](04_performance_analysis.ipynb)** - Metrics deep dive
- **[report_generation.ipynb](report_generation.ipynb)** - Professional reports

### Live Trading
- **[09_live_paper_trading.ipynb](09_live_paper_trading.ipynb)** - Paper trading

---

## 🎓 By Skill Level

### Beginner (3-8 minutes each)
Learn the fundamentals of backtesting with RustyBT.

| Notebook | Topic | Time | What You'll Learn |
|----------|-------|------|-------------------|
| [01_getting_started.ipynb](01_getting_started.ipynb) | First backtest | 3 min | Setup, simple strategy, visualization |
| [02_data_ingestion.ipynb](02_data_ingestion.ipynb) | Data sources | 5 min | yfinance, CCXT, CSV import |
| [03_strategy_development.ipynb](03_strategy_development.ipynb) | Basic strategies | 8 min | MA crossover, mean reversion, momentum |
| [equity_backtest_yfinance.ipynb](equity_backtest_yfinance.ipynb) | Stock backtest | 5 min | Complete stock strategy example |
| [crypto_backtest_ccxt.ipynb](crypto_backtest_ccxt.ipynb) | Crypto backtest | 6 min | Complete crypto strategy example |

### Intermediate (5-12 minutes each)
Master optimization, validation, and portfolio management.

| Notebook | Topic | Time | What You'll Learn |
|----------|-------|------|-------------------|
| [04_performance_analysis.ipynb](04_performance_analysis.ipynb) | Metrics | 5 min | Sharpe, Sortino, Calmar, drawdowns |
| [05_optimization.ipynb](05_optimization.ipynb) | Optimization | 8 min | Grid search, Bayesian optimization |
| [06_walk_forward.ipynb](06_walk_forward.ipynb) | Validation | 10 min | Walk-forward testing, degradation |
| [07_risk_analytics.ipynb](07_risk_analytics.ipynb) | Risk | 8 min | VaR, CVaR, beta, correlations |
| [08_portfolio_construction.ipynb](08_portfolio_construction.ipynb) | Portfolios | 10 min | Multi-asset, rebalancing, allocation |
| [09_live_paper_trading.ipynb](09_live_paper_trading.ipynb) | Live trading | 10 min | Paper broker, real-time testing |
| [15_monte_carlo_basics.ipynb](15_monte_carlo_basics.ipynb) 🆕 | Monte Carlo | 8 min | Data permutation, noise infusion |
| [16_sensitivity_analysis_basics.ipynb](16_sensitivity_analysis_basics.ipynb) 🆕 | Sensitivity | 6 min | Parameter stability, stable regions |

### Advanced (12-20 minutes each)
Combine multiple techniques for production-ready systems.

| Notebook | Topic | Time | What You'll Learn |
|----------|-------|------|-------------------|
| [10_full_workflow.ipynb](10_full_workflow.ipynb) ⭐ | Complete workflow | 15 min | End-to-end pipeline |
| [11_pipeline_deep_dive.ipynb](11_pipeline_deep_dive.ipynb) | Pipeline API | 15 min | Factors, filters, custom terms |
| [12_advanced_order_management.ipynb](12_advanced_order_management.ipynb) | Orders | 12 min | Complex orders, execution models |
| [13_portfolio_optimization_walk_forward.ipynb](13_portfolio_optimization_walk_forward.ipynb) | Portfolio + WF | 15 min | Portfolio optimization with validation |
| [14_multi_timeframe_strategies.ipynb](14_multi_timeframe_strategies.ipynb) | Multi-timeframe | 12 min | Combining multiple timeframes |
| [report_generation.ipynb](report_generation.ipynb) | Reporting | 8 min | Professional PDF/HTML reports |

---

## 🔄 Common Workflows

### Workflow 1: From Idea to Validated Strategy
**Goal:** Take a strategy idea from concept to validated parameters

1. [03_strategy_development.ipynb](03_strategy_development.ipynb) - Implement the strategy
2. [05_optimization.ipynb](05_optimization.ipynb) - Find optimal parameters
3. [16_sensitivity_analysis_basics.ipynb](16_sensitivity_analysis_basics.ipynb) 🆕 - Check parameter stability
4. [06_walk_forward.ipynb](06_walk_forward.ipynb) - Validate with walk-forward
5. [15_monte_carlo_basics.ipynb](15_monte_carlo_basics.ipynb) 🆕 - Test robustness

**Estimated Time:** 45 minutes

### Workflow 2: Multi-Strategy Portfolio System
**Goal:** Build a portfolio of multiple strategies with dynamic allocation

1. [03_strategy_development.ipynb](03_strategy_development.ipynb) - Create sub-strategies
2. [05_optimization.ipynb](05_optimization.ipynb) - Optimize each strategy
3. [08_portfolio_construction.ipynb](08_portfolio_construction.ipynb) - Combine strategies
4. [13_portfolio_optimization_walk_forward.ipynb](13_portfolio_optimization_walk_forward.ipynb) - Optimize allocation

**Estimated Time:** 55 minutes

### Workflow 3: Factor-Based Quantitative Strategy
**Goal:** Build a sophisticated factor-based strategy

1. [11_pipeline_deep_dive.ipynb](11_pipeline_deep_dive.ipynb) - Learn Pipeline API
2. [03_strategy_development.ipynb](03_strategy_development.ipynb) - Implement factor strategy
3. [05_optimization.ipynb](05_optimization.ipynb) - Optimize factor parameters
4. [07_risk_analytics.ipynb](07_risk_analytics.ipynb) - Analyze risk exposures

**Estimated Time:** 50 minutes

### Workflow 4: Production Deployment Preparation
**Goal:** Prepare strategy for live trading

1. [06_walk_forward.ipynb](06_walk_forward.ipynb) - Validate robustness
2. [15_monte_carlo_basics.ipynb](15_monte_carlo_basics.ipynb) 🆕 - Stress test
3. [12_advanced_order_management.ipynb](12_advanced_order_management.ipynb) - Configure execution
4. [09_live_paper_trading.ipynb](09_live_paper_trading.ipynb) - Test in paper trading
5. [report_generation.ipynb](report_generation.ipynb) - Generate documentation

**Estimated Time:** 60 minutes

---

## 🔍 By Use Case

### Use Case: Cryptocurrency Trading
1. [crypto_backtest_ccxt.ipynb](crypto_backtest_ccxt.ipynb) - Get started with crypto
2. [02_data_ingestion.ipynb](02_data_ingestion.ipynb) - CCXT data adapter
3. [12_advanced_order_management.ipynb](12_advanced_order_management.ipynb) - Handle crypto-specific execution

### Use Case: Stock/ETF Trading
1. [equity_backtest_yfinance.ipynb](equity_backtest_yfinance.ipynb) - Get started with stocks
2. [11_pipeline_deep_dive.ipynb](11_pipeline_deep_dive.ipynb) - Factor-based stock selection
3. [08_portfolio_construction.ipynb](08_portfolio_construction.ipynb) - Build stock portfolios

### Use Case: Quantitative Research
1. [11_pipeline_deep_dive.ipynb](11_pipeline_deep_dive.ipynb) - Pipeline for research
2. [16_sensitivity_analysis_basics.ipynb](16_sensitivity_analysis_basics.ipynb) 🆕 - Parameter analysis
3. [15_monte_carlo_basics.ipynb](15_monte_carlo_basics.ipynb) 🆕 - Statistical validation
4. [07_risk_analytics.ipynb](07_risk_analytics.ipynb) - Risk decomposition

### Use Case: Automated Trading System
1. [10_full_workflow.ipynb](10_full_workflow.ipynb) - Complete system design
2. [09_live_paper_trading.ipynb](09_live_paper_trading.ipynb) - Automation setup
3. [12_advanced_order_management.ipynb](12_advanced_order_management.ipynb) - Execution automation

---

## 📊 Feature Coverage Matrix

| Feature | Basic | Intermediate | Advanced |
|---------|-------|--------------|----------|
| **Data Ingestion** | 02 | - | - |
| **Strategy Development** | 03 | 11 | 14 |
| **Optimization** | 05 | 16 🆕 | 13 |
| **Validation** | 06 | 15 🆕 | 13 |
| **Portfolio** | 08 | 13 | 13 |
| **Risk** | 04 | 07 | 12 |
| **Pipeline** | - | 11 | 11 |
| **Live Trading** | - | 09 | 09 |
| **Reporting** | 04 | report_gen | report_gen |

---

## 🆕 New Additions (November 2025)

### Recently Added Notebooks

**[15_monte_carlo_basics.ipynb](15_monte_carlo_basics.ipynb)**
- Monte Carlo simulation for robustness testing
- Data permutation methods
- Noise infusion techniques
- Confidence interval calculation
- **Why it's useful:** Understand the range of possible outcomes and detect overfitting

**[16_sensitivity_analysis_basics.ipynb](16_sensitivity_analysis_basics.ipynb)**
- Parameter sensitivity analysis
- 1D and 2D sensitivity visualization
- Stability metrics calculation
- Stable region identification
- **Why it's useful:** Choose robust parameters instead of overfit optimal points

---

## 📝 Notes

### Data Bundle Required
Most notebooks require a data bundle to be configured. See **[02_data_ingestion.ipynb](02_data_ingestion.ipynb)** for setup instructions.

### Notebook Execution
All notebooks are designed to be:
- ✅ Executed in order (but can also be standalone)
- ✅ Fully documented with explanations
- ✅ Include expected runtime estimates
- ✅ Validated with current RustyBT API (0.1.2+)

### Getting Help
- **Documentation:** https://rustybt.readthedocs.io
- **GitHub Issues:** https://github.com/rustybt/rustybt/issues
- **Discussions:** https://github.com/rustybt/rustybt/discussions

---

## 🎯 Recommended Learning Sequences

### Sequence 1: Weekend Warrior (6-8 hours)
Perfect for getting productive in one weekend.

**Saturday (3-4 hours):**
- 10_full_workflow.ipynb (complete overview)
- 02_data_ingestion.ipynb (set up data)
- 03_strategy_development.ipynb (build strategies)
- 05_optimization.ipynb (optimize parameters)

**Sunday (3-4 hours):**
- 06_walk_forward.ipynb (validate)
- 15_monte_carlo_basics.ipynb (robustness)
- 16_sensitivity_analysis_basics.ipynb (stability)
- 08_portfolio_construction.ipynb (portfolios)

### Sequence 2: Deep Dive (12-15 hours)
Comprehensive mastery of all features.

**Week 1:** Fundamentals (4-5 hours)
- All beginner notebooks (01-03, equity, crypto)
- Performance analysis (04)
- Full workflow (10)

**Week 2:** Optimization & Validation (4-5 hours)
- Optimization (05)
- Walk-forward (06)
- Monte Carlo (15)
- Sensitivity (16)

**Week 3:** Advanced Features (4-5 hours)
- Pipeline (11)
- Portfolio optimization (13)
- Multi-timeframe (14)
- Risk analytics (07)
- Order management (12)

### Sequence 3: Production Ready (20+ hours)
Build institutional-grade trading systems.

- Complete "Deep Dive" sequence above
- Add live trading (09)
- Add reporting (report_generation)
- Build custom workflows combining techniques
- Implement proprietary strategies
- Deploy with proper risk management

---

## 💡 Tips for Success

1. **Start with 10_full_workflow.ipynb** - It gives you the big picture
2. **Run notebooks sequentially** - Each builds on previous concepts
3. **Experiment with code** - Modify examples to learn by doing
4. **Combine techniques** - The real power is in combining modules
5. **Validate thoroughly** - Use walk-forward + Monte Carlo + sensitivity
6. **Document your work** - Use report generation for reproducibility

---

**Total Available Notebooks:** 17 core tutorials + specialized examples
**Total Estimated Learning Time:** 20-30 hours for complete mastery
**Last Updated:** 2025-11-07
