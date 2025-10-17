# Troubleshooting Guide

Common data management issues and solutions.

## Performance Issues

### Slow Data Loading

**Symptom**: Bundle loading takes too long

**Solutions**:
1. **Enable caching**: Configure CacheManager with appropriate memory limits (see [Caching Guide](caching.md))
2. **Use Parquet format**: Parquet bundles load 5-10x faster than HDF5 (see [Migration Guide](../catalog/migration-guide.md))
3. **Reduce data window**: Load smaller date ranges and use rolling windows in your strategy
4. **Parallel loading**: Enable multi-worker data loading where supported

### Additional Resources

1. **Documentation**: Review [Optimization Guide](optimization.md) for tuning strategies
2. **Caching**: See [Caching API](caching.md) for cache configuration
3. **Community**: Ask on GitHub Discussions
4. **Bug Reports**: File issue on GitHub

## See Also

- [Caching](caching.md) - Cache configuration
- [Optimization](optimization.md) - Performance tuning
- [Data Catalog](../catalog/bundle-system.md) - Bundle management
