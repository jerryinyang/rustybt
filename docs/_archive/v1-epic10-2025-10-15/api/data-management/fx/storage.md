# FX Rate Storage

Comparison of FX rate storage methods: In-Memory vs HDF5.

## Storage Comparison

| Feature | InMemoryFXRateReader | HDF5FXRateReader |
|---------|---------------------|------------------|
| **Speed** | ⚡⚡⚡ Fastest | ⚡⚡ Fast |
| **Capacity** | Limited by RAM | ~TB scale |
| **Persistence** | ❌ No | ✅ Yes |
| **Setup** | Simple dictionary | HDF5 file required |
| **Use Case** | Testing, prototyping | Production |

## In-Memory Storage

```python
from rustybt.data.fx import InMemoryFXRateReader
import pandas as pd

# Create rate data structure
data = {
    'mid': {  # Rate name
        'USD': pd.DataFrame({  # Quote currency
            'EUR': [1.08, 1.09, 1.10],  # Base currencies
            'GBP': [1.25, 1.26, 1.27],
        }, index=pd.date_range('2024-01-01', periods=3))
    }
}

reader = InMemoryFXRateReader(data=data, default_rate='mid')
```

**Pros**:
- Instant access
- No I/O overhead
- Simple setup

**Cons**:
- Not persistent
- Limited by memory
- Rebuild on restart

## HDF5 Storage

```python
from rustybt.data.fx import HDF5FXRateWriter, HDF5FXRateReader

# Write rates
writer = HDF5FXRateWriter('/path/to/fx_rates.h5')
writer.write(
    rate='mid',
    quote='USD',
    rates=df  # DataFrame with dates index, currency columns
)

# Read rates
reader = HDF5FXRateReader('/path/to/fx_rates.h5')
```

**Pros**:
- Persistent storage
- Efficient compression
- Fast random access
- Scalable to large datasets

**Cons**:
- File management required
- Initial write overhead
- More complex setup

## HDF5 File Structure

```
fx_rates.h5
├── /data
│   ├── /mid
│   │   ├── /USD
│   │   │   └── /rates (2D array)
│   │   ├── /EUR
│   │   │   └── /rates (2D array)
│   ├── /bid
│   │   └── ...
│   └── /ask
│       └── ...
└── /index
    ├── /dts (timestamps)
    └── /currencies (currency codes)
```

## See [FX Overview](overview.md) for usage examples.
