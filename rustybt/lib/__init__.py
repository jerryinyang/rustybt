# Lazy imports to avoid circular dependencies
# These modules will be imported when accessed
__all__ = ["labelarray", "adjusted_array", "normalize", "quantiles"]


def __getattr__(name):
    if name == "labelarray":
        from . import labelarray

        return labelarray
    elif name == "adjusted_array":
        from . import adjusted_array

        return adjusted_array
    elif name == "normalize":
        from . import normalize

        return normalize
    elif name == "quantiles":
        from . import quantiles

        return quantiles
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
