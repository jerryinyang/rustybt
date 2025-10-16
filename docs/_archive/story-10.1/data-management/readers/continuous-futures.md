# Continuous Futures

Continuous futures readers construct synthetic continuous contracts from individual futures contracts.

## Overview

Futures contracts expire, requiring "rolling" to the next contract. Continuous futures provide seamless historical data.

## Roll Methods

### Front Contract (Default)

Always use the nearest-to-expiry contract:

### Volume-Based Roll

Roll when next contract has higher volume:

```python
continuous_data = reader.get_history(
    root_symbol='ES',  # S&P 500 E-mini
    roll_style='volume',
    roll_days_before_expiry=5  # Roll 5 days before expiry
)
```

### Calendar Roll

Roll on fixed schedule:

```python
continuous_data = reader.get_history(
    root_symbol='GC',  # Gold
    roll_style='calendar',
    roll_day=25  # Roll on 25th of roll month
)
```

## See [Data Portal](data-portal.md) for futures data access in strategies.
