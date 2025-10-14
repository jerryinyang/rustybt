# Finance API Reference

**Last Updated**: 2024-10-11

## Overview

The Finance module provides core financial modeling including commission models, slippage models, order management, and transaction costs. It supports both traditional (float) and Decimal-based arithmetic for financial accuracy.

---

## Commission Models

Commission models calculate transaction costs based on order execution.

### CommissionModel (Abstract Base Class)

Base class for all commission models.

```python
# Code example removed - API does not exist
```python

borrow = BorrowCost(
    annual_rate=0.02  # 2% annual borrow rate
)
```

### OvernightFinancing

Model overnight financing costs for leveraged positions.

```python
# Code example removed - API does not exist
```

---

## Best Practices

### Commission Selection

| Broker Type | Recommended Model | Example |
|-------------|-------------------|---------|
| Interactive Brokers | `PerShare` | 0.005/share, $1 min |
| TD Ameritrade | `PerTrade` | $0 flat |
| Futures Broker | `PerContract` | $0.85/contract |
| Crypto Exchange | `PerDollar` | 0.1% of value |

### Slippage Selection

| Strategy Type | Recommended Model | Settings |
|---------------|-------------------|----------|
| Low Frequency | `FixedSlippage` | 0.01% - 0.05% |
| High Frequency | `VolumeShareSlippage` | 2.5% volume limit |
| Large Orders | `VolumeShareSlippage` | Lower volume limit |
| Crypto | `FixedSlippage` | 0.05% - 0.1% |

### Decimal Precision

Use Decimal models when:
- High precision required (regulatory reporting)
- Large position sizes
- Long-running strategies
- Audit compliance needed

---

## See Also

- [Slippage Models Tutorial](../../examples/slippage_models_tutorial.py)
- [Borrow Cost Tutorial](../../examples/borrow_cost_tutorial.py)
- [Overnight Financing Tutorial](../../examples/overnight_financing_tutorial.py)
- [Decimal Precision Guide](../guides/decimal-precision-configuration.md)
