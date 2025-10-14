# Bundle Metadata

Bundle metadata tracks data quality, lineage, and versioning information.

## Metadata Fields

- `bundle_name`: Bundle identifier
- `source_type`: Data adapter type
- `source_url`: Data source URL
- `data_version`: Version string
- `row_count`: Total rows
- `start_date`: Coverage start
- `end_date`: Coverage end
- `validation_passed`: Quality check status
- `ohlcv_violations`: Relationship violations
- `missing_days_count`: Missing data days
- `outlier_count`: Statistical outliers

## Querying Metadata

```python
from rustybt.data.bundles.metadata import BundleMetadata

# Get metadata
metadata = BundleMetadata.get('my_bundle')

# Check quality
if metadata['validation_passed']:
    print("Data quality OK")
else:
    print(f"Issues: {metadata['ohlcv_violations']} violations")
```

## Updating Metadata

```python
BundleMetadata.update(
    'my_bundle',
    data_version='2.0',
    custom_field='custom_value'
)
```

## See [Catalog Overview](overview.md) for complete guide.
