"""Adapter registration and auto-discovery system.

This module provides a registry for data adapters with support for
dynamic registration and auto-discovery of adapter classes.
"""

import importlib
import pkgutil

import structlog

from rustybt.data.adapters.base import BaseDataAdapter

logger = structlog.get_logger()


class AdapterRegistry:
    """Registry for data adapters with auto-discovery.

    Provides centralized registration and lookup of data adapter classes.
    Supports both manual registration and automatic discovery of adapters
    in the adapters package.

    Attributes:
        _adapters: Dictionary mapping adapter names to adapter classes

    Example:
        >>> # Register adapter manually
        >>> AdapterRegistry.register(MyAdapter)
        >>>
        >>> # Auto-discover all adapters
        >>> AdapterRegistry.discover_adapters()
        >>>
        >>> # Get adapter by name
        >>> adapter_class = AdapterRegistry.get_adapter("MyAdapter")
        >>> adapter = adapter_class(name="my_adapter")
    """

    _adapters: dict[str, type[BaseDataAdapter]] = {}

    @classmethod
    def register(cls, adapter_class: type[BaseDataAdapter]) -> None:
        """Register adapter class.

        Args:
            adapter_class: Adapter class to register (must inherit from BaseDataAdapter)

        Raises:
            TypeError: If adapter_class does not inherit from BaseDataAdapter

        Example:
            >>> class MyAdapter(BaseDataAdapter):
            ...     pass
            >>> AdapterRegistry.register(MyAdapter)
        """
        if not issubclass(adapter_class, BaseDataAdapter):
            raise TypeError(
                f"Adapter class must inherit from BaseDataAdapter, got {adapter_class.__name__}"
            )

        adapter_name = adapter_class.__name__
        cls._adapters[adapter_name] = adapter_class

        logger.info(
            "adapter_registered",
            adapter_name=adapter_name,
            adapter_class=adapter_class.__module__ + "." + adapter_class.__name__,
        )

    @classmethod
    def get_adapter(cls, name: str) -> type[BaseDataAdapter]:
        """Get adapter class by name.

        Args:
            name: Name of adapter class to retrieve

        Returns:
            Adapter class

        Raises:
            ValueError: If adapter with given name is not found

        Example:
            >>> adapter_class = AdapterRegistry.get_adapter("MyAdapter")
            >>> adapter = adapter_class(name="instance")
        """
        if name not in cls._adapters:
            available = ", ".join(cls._adapters.keys())
            raise ValueError(f"Adapter '{name}' not found. Available adapters: {available}")
        return cls._adapters[name]

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names.

        Returns:
            List of registered adapter names

        Example:
            >>> adapters = AdapterRegistry.list_adapters()
            >>> print(f"Available adapters: {adapters}")
        """
        return list(cls._adapters.keys())

    @classmethod
    def discover_adapters(cls) -> int:
        """Auto-discover adapters in adapters/ directory.

        Scans the rustybt.data.adapters package for adapter classes
        and automatically registers them.

        Returns:
            Number of adapters discovered and registered

        Example:
            >>> count = AdapterRegistry.discover_adapters()
            >>> print(f"Discovered {count} adapters")
        """
        import rustybt.data.adapters

        discovered_count = 0

        try:
            # Iterate through all modules in adapters package
            for _, module_name, _ in pkgutil.iter_modules(rustybt.data.adapters.__path__):
                # Skip base and registry modules
                if module_name in ("base", "registry", "api_provider_base"):
                    continue

                try:
                    # Import module
                    module = importlib.import_module(f"rustybt.data.adapters.{module_name}")

                    # Find adapter classes in module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)

                        # Check if it's a class that inherits from BaseDataAdapter
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseDataAdapter)
                            and attr != BaseDataAdapter
                        ):
                            # Register if not already registered
                            if attr_name not in cls._adapters:
                                cls.register(attr)
                                discovered_count += 1

                except ImportError as e:
                    logger.warning(
                        "adapter_discovery_import_failed",
                        module_name=module_name,
                        error=str(e),
                    )

        except Exception as e:
            logger.error("adapter_discovery_failed", error=str(e))

        logger.info(
            "adapter_discovery_complete",
            discovered_count=discovered_count,
            total_adapters=len(cls._adapters),
        )

        return discovered_count

    @classmethod
    def clear(cls) -> None:
        """Clear all registered adapters.

        Useful for testing to reset registry state.

        Example:
            >>> AdapterRegistry.clear()
            >>> assert len(AdapterRegistry.list_adapters()) == 0
        """
        cls._adapters = {}
        logger.debug("adapter_registry_cleared")
