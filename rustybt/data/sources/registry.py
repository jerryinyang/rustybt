"""DataSource registry for auto-discovery and factory methods.

This module provides dynamic discovery of all DataSource implementations
and factory methods for creating source instances by name.
"""

from typing import Any, ClassVar

import structlog

from rustybt.data.sources.base import DataSource

logger = structlog.get_logger()


class DataSourceRegistry:
    """Registry for dynamic DataSource discovery and instantiation.

    Automatically discovers all DataSource implementations at runtime and
    provides factory methods for creating instances by name.

    Example:
        >>> # List available sources
        >>> sources = DataSourceRegistry.list_sources()
        >>> print(sources)  # ['yfinance', 'ccxt', 'polygon', 'alpaca', 'alphavantage', 'csv']
        >>>
        >>> # Get source instance
        >>> source = DataSourceRegistry.get_source("yfinance")
        >>>
        >>> # Get source metadata
        >>> info = DataSourceRegistry.get_source_info("yfinance")
        >>> print(info['supports_live'])  # False
    """

    _sources: ClassVar[dict[str, type[DataSource]]] = {}
    _discovered: ClassVar[bool] = False

    @classmethod
    def _discover_sources(cls) -> None:
        """Auto-discover all DataSource implementations.

        Walks the DataSource class hierarchy to find all concrete implementations.
        Extracts source names from class names (e.g., YFinanceAdapter -> 'yfinance').

        This method is called automatically on first access to ensure sources
        are discovered lazily.
        """
        if cls._discovered:
            return

        logger.debug("datasource_discovery_start")

        # Import all adapter modules to trigger class registration
        # This ensures __subclasses__() finds all implementations
        try:
            from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter  # noqa: F401
            from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter  # noqa: F401
            from rustybt.data.adapters.ccxt_adapter import CCXTAdapter  # noqa: F401
            from rustybt.data.adapters.csv_adapter import CSVAdapter  # noqa: F401
            from rustybt.data.adapters.polygon_adapter import PolygonAdapter  # noqa: F401
            from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter  # noqa: F401
        except ImportError as e:
            logger.warning("adapter_import_failed", error=str(e))

        # Discover all DataSource subclasses
        for subclass in cls._get_all_subclasses(DataSource):
            # Extract source name from class name
            # Examples:
            #   YFinanceAdapter -> yfinance
            #   CCXTAdapter -> ccxt
            #   PolygonAdapter -> polygon
            class_name = subclass.__name__
            name = class_name.lower().replace("adapter", "").replace("datasource", "")

            # Only register concrete implementations (not abstract classes)
            if not hasattr(subclass, "__abstractmethods__") or not subclass.__abstractmethods__:
                cls._sources[name] = subclass
                logger.debug(
                    "datasource_registered",
                    name=name,
                    class_name=class_name,
                )

        cls._discovered = True
        logger.info(
            "datasource_discovery_complete",
            sources=list(cls._sources.keys()),
            count=len(cls._sources),
        )

    @classmethod
    def _get_all_subclasses(cls, base_class: type) -> list[type]:
        """Recursively get all subclasses of base_class.

        Args:
            base_class: Base class to find subclasses for

        Returns:
            List of all subclasses (including nested subclasses)
        """
        subclasses = []
        for subclass in base_class.__subclasses__():
            subclasses.append(subclass)
            subclasses.extend(cls._get_all_subclasses(subclass))
        return subclasses

    @classmethod
    def get_source(cls, name: str, **config: Any) -> DataSource:
        """Get DataSource instance by name.

        Factory method that creates a new instance of the specified data source.
        Automatically discovers sources on first access.

        Args:
            name: Source name (e.g., 'yfinance', 'ccxt', 'polygon')
            **config: Configuration parameters passed to source constructor

        Returns:
            DataSource instance

        Raises:
            ValueError: If source name is not recognized

        Example:
            >>> # Get YFinance source
            >>> source = DataSourceRegistry.get_source("yfinance")
            >>>
            >>> # Get CCXT source with exchange config
            >>> source = DataSourceRegistry.get_source(
            ...     "ccxt",
            ...     exchange_id="binance",
            ...     api_key="...",
            ...     api_secret="..."
            ... )
        """
        if not cls._discovered:
            cls._discover_sources()

        name_lower = name.lower()

        if name_lower not in cls._sources:
            available = ", ".join(sorted(cls._sources.keys()))
            raise ValueError(f"Unknown data source: '{name}'. Available sources: {available}")

        source_class = cls._sources[name_lower]

        logger.debug(
            "datasource_instantiate",
            name=name_lower,
            class_name=source_class.__name__,
        )

        return source_class(**config)

    @classmethod
    def list_sources(cls) -> list[str]:
        """List all available data source names.

        Returns:
            Sorted list of source names

        Example:
            >>> sources = DataSourceRegistry.list_sources()
            >>> print(sources)
            ['alpaca', 'alphavantage', 'ccxt', 'csv', 'polygon', 'yfinance']
        """
        if not cls._discovered:
            cls._discover_sources()

        return sorted(cls._sources.keys())

    @classmethod
    def get_source_info(cls, name: str) -> dict[str, Any]:
        """Get metadata for a specific data source.

        Args:
            name: Source name (e.g., 'yfinance')

        Returns:
            Dictionary with source metadata including:
            - name: Source name
            - class_name: Python class name
            - source_type: Type from metadata
            - supports_live: Whether live streaming is supported
            - metadata: Full DataSourceMetadata object

        Raises:
            ValueError: If source name is not recognized

        Example:
            >>> info = DataSourceRegistry.get_source_info("yfinance")
            >>> print(f"Supports live: {info['supports_live']}")
            >>> print(f"Data delay: {info['metadata'].data_delay} minutes")
        """
        # Create instance to get metadata
        source = cls.get_source(name)
        metadata = source.get_metadata()

        return {
            "name": name,
            "class_name": source.__class__.__name__,
            "source_type": metadata.source_type,
            "supports_live": metadata.supports_live,
            "auth_required": metadata.auth_required,
            "rate_limit": metadata.rate_limit,
            "data_delay": metadata.data_delay,
            "supported_frequencies": metadata.supported_frequencies,
            "metadata": metadata,
        }

    @classmethod
    def reset(cls) -> None:
        """Reset registry state (mainly for testing).

        Clears discovered sources and forces re-discovery on next access.
        """
        cls._sources.clear()
        cls._discovered = False
        logger.debug("datasource_registry_reset")
