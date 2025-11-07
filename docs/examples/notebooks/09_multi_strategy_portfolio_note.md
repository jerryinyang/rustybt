# Multi-Strategy Portfolio Management

**Note:** The multi-strategy portfolio notebook has been moved to a working Python example.

## Correct Implementation

For multi-strategy portfolio management, please refer to:

**📄 [`docs/examples/portfolio_allocator_tutorial.py`](../portfolio_allocator_tutorial.py)**

This example demonstrates the correct usage of `PortfolioAllocator` with:
- ✅ Proper strategy class structure
- ✅ Independent ledger management
- ✅ Correct API usage
- ✅ Working code that executes successfully

## Why No Notebook?

The `PortfolioAllocator` API is designed for standalone strategy classes, not `TradingAlgorithm` subclasses. This makes it better suited for:
- Python scripts
- Production deployment
- Complex multi-strategy systems

Notebooks are better for:
- Single-strategy exploration
- Interactive backtesting
- Educational purposes

## Quick Example

```python
from decimal import Decimal
from rustybt.portfolio.allocator import PortfolioAllocator

# Simple strategy class
class MyStrategy:
    def handle_data(self, ledger, data):
        # ledger: DecimalLedger for this strategy
        # data: Market data dict
        pass

# Create portfolio
portfolio = PortfolioAllocator(
    total_capital=Decimal("1000000"),
    name="My Portfolio"
)

# Add strategy with 40% allocation
portfolio.add_strategy(
    strategy_id="strategy1",
    strategy=MyStrategy(),
    allocation_pct=Decimal("0.40")
)

# Execute bar
portfolio.execute_bar(timestamp, data)
```

## Key Differences from TradingAlgorithm

| Feature | TradingAlgorithm | PortfolioAllocator Strategy |
|---------|------------------|----------------------------|
| **Base class** | Inherit from `TradingAlgorithm` | Plain Python class |
| **API functions** | `order()`, `order_target_percent()` | Direct ledger access |
| **Execution** | `run_algorithm()` | `portfolio.execute_bar()` |
| **Capital** | Global portfolio | Isolated per strategy |
| **Use case** | Single strategy | Multi-strategy portfolio |

## Related Documentation

- 📖 [Multi-Strategy Portfolio Guide](../../guides/multi-strategy-portfolio-guide.md)
- 📄 [portfolio_allocator_tutorial.py](../portfolio_allocator_tutorial.py) - Working example
- 📄 [allocation_algorithms_tutorial.py](../allocation_algorithms_tutorial.py) - Allocation methods
- 📓 [Notebook 08: Portfolio Construction](08_portfolio_construction.ipynb) - Single-strategy multi-asset

## See Also

For simple multi-asset portfolios using a single strategy, see:
- **[Notebook 08: Portfolio Construction](08_portfolio_construction.ipynb)** - Manages multiple assets with one strategy

For advanced portfolio optimization:
- **[Notebook 13: Portfolio Optimization + Walk-Forward](advanced/13_portfolio_optimization_walk_forward.ipynb)**
