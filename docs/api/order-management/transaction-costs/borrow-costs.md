# Borrow Costs and Short Selling

Complete guide to modeling borrow costs for short selling in RustyBT.

## Overview

When short selling, traders must borrow shares and pay fees to the lender. RustyBT models these costs to provide realistic short selling simulations:

- **Borrow Fee**: Daily or annual percentage fee on borrowed shares
- **Hard-to-Borrow (HTB) Premium**: Additional fees for illiquid stocks
- **Rebate Rates**: Interest earned on short sale proceeds (collateral)
- **Forced Buy-Ins**: Costs when shares become unavailable

## Why Model Borrow Costs?

**Without borrow cost modeling**:
- ✗ Short selling appears "free"
- ✗ Overestimates profitability of short strategies
- ✗ Ignores major cost component (can exceed 50% annualized for HTB stocks)

**With borrow costs**:
- ✓ Realistic short strategy performance
- ✓ Accurate cost of carry for short positions
- ✓ Better risk-adjusted returns
- ✓ Proper comparison of long vs short strategies

## Borrow Fee Basics

### Annual Borrow Rate

Expressed as annual percentage of stock value.

```python
# Code example removed - API does not exist
```

## Asset-Specific Borrow Rates

Different stocks have different borrow rates based on availability.

### Dynamic Borrow Rates

```python
# Code example removed - API does not exist
```

### Market Cap Based Rates

Typical borrow rates by market capitalization.

```python
# Code example removed - API does not exist
```

## Time-Varying Borrow Rates

Borrow rates change over time based on supply/demand.

### Historical Borrow Rate Data

```python
# Code example removed - API does not exist
```

## Short Rebate Rates

Interest earned on collateral from short sales.

### Rebate Model

```python
# Code example removed - API does not exist
```

## Hard-to-Borrow (HTB) Scenarios

### Availability-Based Costs

```python
# Code example removed - API does not exist
```

### Forced Buy-In Costs

```python
# Code example removed - API does not exist
```

## Strategy Integration

### Track Borrow Costs in Strategy

```python
# Code example removed - API does not exist
```

## Typical Borrow Rates

### By Asset Class

| Asset Type | Typical Annual Rate | Notes |
|------------|---------------------|-------|
| Large Cap Stocks | 0.3% - 1% | Easy to borrow, liquid |
| Mid Cap Stocks | 1% - 5% | Moderate availability |
| Small Cap Stocks | 5% - 15% | Limited availability |
| Penny Stocks | 15% - 50%+ | Very hard to borrow |
| ETFs | 0.1% - 0.5% | Very easy to borrow |
| Crypto | Varies | 1% - 100%+ depending on exchange |

### By Short Interest

| Short Interest % | Typical Rate | Classification |
|------------------|--------------|----------------|
| 0% - 2% | 0.3% - 1% | Easy to borrow |
| 2% - 5% | 1% - 5% | Moderate |
| 5% - 10% | 5% - 15% | Hard to borrow (HTB) |
| 10% - 20% | 15% - 50% | Very HTB |
| 20%+ | 50% - 1000%+ | Extreme HTB, squeeze risk |

## Best Practices

### ✅ DO

1. **Use Realistic Rates**: Match actual broker rates for your asset class
2. **Consider Market Conditions**: Borrow rates spike during short squeezes
3. **Track Total Costs**: Monitor cumulative borrow costs over time
4. **Factor Into Sizing**: Reduce position size for high borrow cost stocks
5. **Monitor Availability**: Check short interest and availability regularly

### ❌ DON'T

1. **Ignore Borrow Costs**: Can eliminate strategy profitability
2. **Use Same Rate for All**: Rates vary significantly by asset
3. **Forget Rebates**: Can offset some or all borrow costs
4. **Overlook HTB Risk**: Forced buy-ins can be very expensive
5. **Assume Static Rates**: Borrow costs change based on supply/demand

## Example: Complete Short Strategy with Costs

```python
# Code example removed - API does not exist
```

## Related Documentation

- [Financing Costs](financing.md) - Overnight and leverage financing
- [Slippage Models](slippage.md) - Execution costs
- [Commission Models](commissions.md) - Transaction fees
- [Transaction Costs Overview](README.md) - Complete cost modeling

## Next Steps

1. Study [Financing Costs](financing.md) for overnight position costs
2. Review [Complete Cost Modeling](README.md) for integrated approach
3. Test short strategies with realistic borrow costs
