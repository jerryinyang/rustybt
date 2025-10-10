# Bundle Metadata API Reference

## BundleMetadata

Unified metadata storage for bundles (replaces `DataCatalog` and `ParquetMetadataCatalog`).

```python
from rustybt.data.bundles import BundleMetadata
import pandas as pd

# Load metadata
metadata = BundleMetadata(bundle_name="my-bundle")

# Add symbol
metadata.add_symbol(
    symbol="AAPL",
    start_date=pd.Timestamp("2023-01-01"),
    end_date=pd.Timestamp("2023-12-31"),
    frequency="daily",
    row_count=252
)

# Query metadata
symbols = metadata.list_symbols()
info = metadata.get_symbol_info("AAPL")

# Get quality metrics
metrics = metadata.get_quality_metrics()
print(f"Coverage: {metrics['completeness']}%")

# CLI commands
```bash
# List bundles
rustybt bundle list

# Show bundle info
rustybt bundle info my-bundle

# Validate bundle
rustybt bundle validate my-bundle
```

---

**See Also**:
- [Data Ingestion Guide](../guides/data-ingestion.md)
- [Migrating to Unified Data](../guides/migrating-to-unified-data.md)
