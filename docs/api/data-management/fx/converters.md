# Currency Converters

Utilities for converting values between currencies.

## Basic Conversion

```python
def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    dt: pd.Timestamp,
    fx_reader,
    rate: str = 'mid'
) -> float:
    """Convert amount between currencies."""
    if from_currency == to_currency:
        return amount

    fx_rate = fx_reader.get_rate_scalar(
        rate=rate,
        quote=to_currency,
        base=from_currency,
        dt=dt
    )

    return amount * fx_rate
```

## Batch Conversion

```python
def convert_series(
    amounts: pd.Series,
    from_currency: str,
    to_currency: str,
    fx_reader
) -> pd.Series:
    """Convert time series of amounts."""
    rates = fx_reader.get_rates(
        rate='mid',
        quote=to_currency,
        bases=np.array([from_currency]),
        dts=amounts.index
    )

    return amounts * rates[:, 0]
```

## Portfolio Conversion

```python
def portfolio_to_base_currency(
    positions: dict,  # {asset: (amount, currency)}
    base_currency: str,
    dt: pd.Timestamp,
    fx_reader
) -> dict:
    """Convert all positions to base currency."""
    converted = {}

    for asset, (amount, currency) in positions.items():
        if currency == base_currency:
            converted[asset] = amount
        else:
            rate = fx_reader.get_rate_scalar(
                rate='mid',
                quote=base_currency,
                base=currency,
                dt=dt
            )
            converted[asset] = amount * rate

    return converted
```

## See [FX Overview](overview.md) for complete examples.
