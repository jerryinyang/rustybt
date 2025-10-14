# Data Catalog Overview

The Data Catalog system provides centralized management of data bundles, metadata tracking, and data versioning for RustyBT.

## Overview

The catalog system consists of three main components:

1. **Bundle Registry**: Manages data bundle registration and discovery
2. **Metadata Tracking**: Tracks data quality, lineage, and versioning
3. **Bundle Storage**: Handles physical storage of market data

## Architecture

```
┌──────────────────────────────────────────────────┐
│              Trading Strategy                    │
└─────────────────┬────────────────────────────────┘
                  │
          ┌───────▼────────┐
          │  Data Portal   │
          └───────┬────────┘
                  │
          ┌───────▼────────┐
          │  Data Catalog  │
          │                │
          │  ┌──────────┐  │
          │  │ Registry │  │
          │  ├──────────┤  │
          │  │ Metadata │  │
          │  ├──────────┤  │
          │  │ Storage  │  │
          │  └──────────┘  │
          └────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐    ┌────▼────┐   ┌───▼────┐
│Parquet│    │  HDF5   │   │ bcolz  │
└───────┘    └─────────┘   └────────┘
```

## Quick Start

### Registering a Bundle

```python
# Code example removed - API does not exist
```

## Bundle Registry

### Listing Available Bundles

```python
# Code example removed - API does not exist
```

### Querying Metadata

```python
# Code example removed - API does not exist
```

### Quality Metrics

```python
# Code example removed - API does not exist
```

### 3. Regular Ingestion

```python
# Code example removed - API does not exist
```

## Troubleshooting

### Issue: Bundle Not Found

```python
# Code example removed - API does not exist
```

## Next Steps

- **[Bundle Creation](bundles.md)** - Detailed bundle registration and ingestion
- **[Metadata API](metadata.md)** - Comprehensive metadata management
- **[Migration Guide](migration.md)** - Migrating from HDF5/bcolz to Parquet

## See Also

- [Data Adapters](../adapters/overview.md) - Data sources
- [Bar Readers](../readers/bar-readers.md) - Reading bundle data
- [Data Portal](../readers/data-portal.md) - Unified data access
