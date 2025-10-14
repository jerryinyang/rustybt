# Caching API Reference

Wraps any `DataSource` with transparent caching to Parquet bundles.

```python
# Code example removed - API does not exist
```python

policy = HybridFreshnessPolicy(
    market_close_time="16:00",
    timezone="America/New_York",
    ttl_seconds=300  # 5 minutes during market hours
)
```

---

**See Also**:
- [Caching Guide](../guides/caching-guide.md)
- [DataSource API](datasource-api.md)
