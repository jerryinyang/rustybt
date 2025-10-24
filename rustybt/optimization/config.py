"""
Performance optimization configuration system.

This module provides configuration management for optimization thresholds,
caching strategies, and sequential evaluation parameters.

Constitutional requirements:
- CR-001: Decimal precision for all numeric thresholds
- CR-004: Complete type hints
"""

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from rustybt.benchmarks.models import PerformanceThreshold
from rustybt.benchmarks.threshold import create_threshold


@dataclass
class OptimizationConfig:
    """
    Centralized configuration for performance optimization framework.

    This configuration system manages thresholds for different workflow types
    and dataset sizes, allowing consistent evaluation criteria across the
    optimization process.

    Attributes:
        thresholds: Mapping of (workflow_type, dataset_size) -> PerformanceThreshold
        enable_debug_logging: Enable detailed debug output (default: False)
        benchmark_output_dir: Directory for benchmark results (default: 'benchmark-results')
        sequential_evaluation_goal_percent: Target cumulative improvement (default: 40%)
        stop_on_diminishing_returns: Stop after 2 consecutive rejections (default: True)
        cache_size_gb: Data cache size limit in GB (default: 2.0, Story X4.4)
        enable_caching: Enable asset list and data caching (default: True, Story X4.4)
        lru_maxsize: LRU cache max size for asset lists (default: 128, Story X4.4)
        enable_bundle_pooling: Enable bundle connection pooling (default: True, Story X4.6)
        cache_size_limit: History cache size limit in bytes (default: 200MB, Story X4.5)
        tier2_maxsize: Maximum LRU cache entries for tier2 (default: 256, Story X4.5)
        permanent_windows: Bar counts for permanent tier1 cache (default: [20, 50, 200], Story X4.5)
        enable_history_cache: Enable multi-tier DataPortal history cache (default: True, Story X4.5)
        enable_shared_bundle_context: Enable shared bundle context optimization (default: False, Story X4.7 Phase 6B)
        enable_persistent_worker_pool: Enable persistent worker pool optimization (default: False, Story X4.7 Phase 6B)
    """

    thresholds: Dict[tuple[str, str], PerformanceThreshold]
    enable_debug_logging: bool = False
    benchmark_output_dir: str = "benchmark-results"
    sequential_evaluation_goal_percent: Decimal = Decimal("40.0")
    stop_on_diminishing_returns: bool = True
    # Story X4.4: User code optimization caching parameters
    cache_size_gb: Decimal = Decimal("2.0")
    enable_caching: bool = True
    lru_maxsize: int = 128
    # Story X4.6: Bundle pooling parameters
    enable_bundle_pooling: bool = True
    max_bundle_pool_size: int = 100  # Maximum bundles in pool before LRU eviction
    # Story X4.5: DataPortal history cache parameters (Layer 2 optimization)
    cache_size_limit: int = 200 * 1024 * 1024  # 200MB in bytes
    tier2_maxsize: int = 256  # Maximum LRU cache entries
    permanent_windows: tuple[int, ...] = (20, 50, 200)  # Permanent cache windows
    enable_history_cache: bool = True  # Enable multi-tier history cache
    # Story X4.7 Phase 6B: Heavy operations optimization feature flags (74.97% speedup)
    enable_shared_bundle_context: bool = (
        False  # Shared bundle across workers (REJECTED - serialization issues)
    )
    enable_persistent_worker_pool: bool = (
        True  # Persistent worker pool (ACCEPTED - enabled by default)
    )

    def should_use_bundle_pool(self) -> bool:
        """Check if bundle pooling is enabled.

        Returns:
            True if bundle pooling enabled, False otherwise

        Example:
            >>> config = OptimizationConfig.create_default()
            >>> if config.should_use_bundle_pool():
            ...     # Use BundleConnectionPool
            ...     pass
        """
        return self.enable_bundle_pooling

    @classmethod
    def create_default(cls) -> "OptimizationConfig":
        """
        Create default optimization configuration with standard thresholds.

        Default thresholds:
        - 5% minimum improvement for all workflows
        - 95% confidence level (p<0.05)
        - Minimum 10 benchmark runs
        - 2% maximum memory increase

        Returns:
            OptimizationConfig with default settings

        Examples:
            >>> config = OptimizationConfig.create_default()
            >>> grid_search_threshold = config.get_threshold('grid_search', 'production')
            >>> print(grid_search_threshold.min_improvement_percent)
            5.0
        """
        thresholds = {}

        # Grid Search - Production Dataset (default)
        thresholds[("grid_search", "production")] = create_threshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="grid_search",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.95"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("2.0"),
            rationale=(
                "5% threshold for grid search optimization on production datasets. "
                "Balances statistical measurability (>2% noise level) with achievability "
                "for individual optimizations. 2% memory increase limit per AC requirements."
            ),
        )

        # Walk Forward - Production Dataset
        thresholds[("walk_forward", "production")] = create_threshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="walk_forward",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.95"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("2.0"),
            rationale=(
                "5% threshold for walk forward optimization on production datasets. "
                "Same as grid search since workload patterns are similar (multiple backtests)."
            ),
        )

        # Single Backtest - Production Dataset (same memory constraint as AC)
        thresholds[("single_backtest", "production")] = create_threshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="single_backtest",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.95"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("2.0"),
            rationale=(
                "5% threshold for single backtest on production datasets. "
                "2% memory increase limit per AC requirements."
            ),
        )

        # Medium Dataset Configurations (slightly more lenient memory)
        thresholds[("grid_search", "medium")] = create_threshold(
            min_improvement_percent=Decimal("3.0"),
            workflow_type="grid_search",
            dataset_size_category="medium",
            statistical_confidence=Decimal("0.95"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("5.0"),
            rationale=(
                "3% threshold for grid search on medium datasets. "
                "Lower threshold acceptable since measurement noise is lower on smaller workloads."
            ),
        )

        # Small Dataset Configurations (for testing/development)
        thresholds[("grid_search", "small")] = create_threshold(
            min_improvement_percent=Decimal("2.0"),
            workflow_type="grid_search",
            dataset_size_category="small",
            statistical_confidence=Decimal("0.90"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("10.0"),
            rationale=(
                "2% threshold for grid search on small datasets (testing/development). "
                "Lower threshold and confidence level acceptable for development feedback."
            ),
        )

        # Environment variable overrides for debugging
        debug_logging = os.getenv("RUSTYBT_DEBUG_OPTIMIZATION", "").lower() == "true"
        output_dir = os.getenv("RUSTYBT_BENCHMARK_DIR", "benchmark-results")

        # Story X4.4: Environment variable overrides for caching
        cache_size_gb = Decimal(os.getenv("RUSTYBT_CACHE_SIZE_GB", "2.0"))
        enable_caching = os.getenv("RUSTYBT_ENABLE_CACHING", "true").lower() == "true"
        lru_maxsize = int(os.getenv("RUSTYBT_LRU_MAXSIZE", "128"))

        # Story X4.6: Environment variable overrides for bundle pooling
        enable_bundle_pooling = os.getenv("RUSTYBT_ENABLE_BUNDLE_POOLING", "true").lower() == "true"
        max_bundle_pool_size = int(os.getenv("RUSTYBT_MAX_BUNDLE_POOL_SIZE", "100"))

        # Story X4.7 Phase 6B: Environment variable overrides for heavy operations
        enable_shared_bundle_context = (
            os.getenv("RUSTYBT_ENABLE_SHARED_BUNDLE", "false").lower() == "true"
        )
        enable_persistent_worker_pool = (
            os.getenv("RUSTYBT_ENABLE_PERSISTENT_POOL", "false").lower() == "true"
        )

        # Validate cache_size_gb must be positive
        if cache_size_gb <= 0:
            raise ValueError(f"cache_size_gb must be > 0, got {cache_size_gb}")

        # Validate max_bundle_pool_size must be positive
        if max_bundle_pool_size <= 0:
            raise ValueError(f"max_bundle_pool_size must be > 0, got {max_bundle_pool_size}")

        return cls(
            thresholds=thresholds,
            enable_debug_logging=debug_logging,
            benchmark_output_dir=output_dir,
            sequential_evaluation_goal_percent=Decimal("40.0"),
            stop_on_diminishing_returns=True,
            cache_size_gb=cache_size_gb,
            enable_caching=enable_caching,
            lru_maxsize=lru_maxsize,
            enable_bundle_pooling=enable_bundle_pooling,
            max_bundle_pool_size=max_bundle_pool_size,
            enable_shared_bundle_context=enable_shared_bundle_context,
            enable_persistent_worker_pool=enable_persistent_worker_pool,
        )

    @classmethod
    def create_strict(cls) -> "OptimizationConfig":
        """
        Create strict configuration for production validation.

        Strict thresholds:
        - 10% minimum improvement (high bar)
        - 99% confidence level (p<0.01)
        - Minimum 20 benchmark runs (high statistical power)
        - 1% maximum memory increase (tight constraint)

        Returns:
            OptimizationConfig with strict settings

        Examples:
            >>> config = OptimizationConfig.create_strict()
            >>> threshold = config.get_threshold('grid_search', 'production')
            >>> print(threshold.min_improvement_percent)
            10.0
        """
        thresholds = {}

        for workflow_type in ["grid_search", "walk_forward", "single_backtest"]:
            for dataset_size in ["small", "medium", "large", "production"]:
                thresholds[(workflow_type, dataset_size)] = create_threshold(
                    min_improvement_percent=Decimal("10.0"),
                    workflow_type=workflow_type,
                    dataset_size_category=dataset_size,
                    statistical_confidence=Decimal("0.99"),
                    min_sample_size=20,
                    max_memory_increase_percent=Decimal("1.0"),
                    rationale=(
                        f"Strict 10% threshold for {workflow_type} on {dataset_size} datasets. "
                        "High confidence (99%) and large sample size (20) ensure robust decisions."
                    ),
                )

        return cls(
            thresholds=thresholds,
            enable_debug_logging=False,
            benchmark_output_dir="benchmark-results",
            sequential_evaluation_goal_percent=Decimal("50.0"),  # Higher goal
            stop_on_diminishing_returns=True,
            cache_size_gb=Decimal("1.5"),  # Stricter memory limit
            enable_caching=True,
            lru_maxsize=64,  # Smaller cache
            enable_bundle_pooling=True,
            max_bundle_pool_size=50,  # Smaller pool for strict mode
        )

    @classmethod
    def create_lenient(cls) -> "OptimizationConfig":
        """
        Create lenient configuration for experimentation.

        Lenient thresholds:
        - 2% minimum improvement (low bar for exploration)
        - 90% confidence level (p<0.10)
        - Minimum 10 benchmark runs (maintains statistical validity)
        - 10% maximum memory increase (allows some caching overhead)

        Returns:
            OptimizationConfig with lenient settings

        Examples:
            >>> config = OptimizationConfig.create_lenient()
            >>> threshold = config.get_threshold('grid_search', 'small')
            >>> print(threshold.min_improvement_percent)
            2.0
        """
        thresholds = {}

        for workflow_type in ["grid_search", "walk_forward", "single_backtest"]:
            for dataset_size in ["small", "medium", "large", "production"]:
                thresholds[(workflow_type, dataset_size)] = create_threshold(
                    min_improvement_percent=Decimal("2.0"),
                    workflow_type=workflow_type,
                    dataset_size_category=dataset_size,
                    statistical_confidence=Decimal("0.90"),
                    min_sample_size=10,  # Keep at 10 for statistical validity
                    max_memory_increase_percent=Decimal("10.0"),
                    rationale=(
                        f"Lenient 2% threshold for {workflow_type} on {dataset_size} datasets. "
                        "Low threshold and confidence for rapid experimentation feedback."
                    ),
                )

        return cls(
            thresholds=thresholds,
            enable_debug_logging=True,  # Enable debug for experimentation
            benchmark_output_dir="benchmark-results",
            sequential_evaluation_goal_percent=Decimal("20.0"),  # Lower goal
            stop_on_diminishing_returns=False,  # Don't stop early
            cache_size_gb=Decimal("3.0"),  # More lenient memory
            enable_caching=True,
            lru_maxsize=256,  # Larger cache for experimentation
            enable_bundle_pooling=True,
            max_bundle_pool_size=200,  # Larger pool for experimentation
        )

    def get_threshold(
        self, workflow_type: str, dataset_size_category: str = "production"
    ) -> PerformanceThreshold:
        """
        Get threshold configuration for specific workflow and dataset size.

        Args:
            workflow_type: Type of workflow ('grid_search', 'walk_forward', 'single_backtest')
            dataset_size_category: Dataset size ('small', 'medium', 'large', 'production')

        Returns:
            PerformanceThreshold for the specified configuration

        Raises:
            KeyError: If configuration for workflow/dataset combination not found

        Examples:
            >>> config = OptimizationConfig.create_default()
            >>> threshold = config.get_threshold('grid_search', 'production')
            >>> print(f"Threshold: {threshold.min_improvement_percent}%")
            Threshold: 5.0%
        """
        key = (workflow_type, dataset_size_category)
        if key not in self.thresholds:
            raise KeyError(
                f"No threshold configured for workflow_type='{workflow_type}', "
                f"dataset_size_category='{dataset_size_category}'. "
                f"Available configurations: {list(self.thresholds.keys())}"
            )
        return self.thresholds[key]

    def set_threshold(
        self,
        threshold: PerformanceThreshold,
        workflow_type: Optional[str] = None,
        dataset_size_category: Optional[str] = None,
    ) -> None:
        """
        Set or update threshold configuration.

        Args:
            threshold: PerformanceThreshold to set
            workflow_type: Override workflow_type from threshold (optional)
            dataset_size_category: Override dataset_size_category (optional)

        Examples:
            >>> config = OptimizationConfig.create_default()
            >>> custom_threshold = create_threshold(
            ...     min_improvement_percent=Decimal('7.5'),
            ...     workflow_type='grid_search'
            ... )
            >>> config.set_threshold(custom_threshold)
        """
        wf_type = workflow_type or threshold.workflow_type
        ds_category = dataset_size_category or threshold.dataset_size_category

        self.thresholds[(wf_type, ds_category)] = threshold

    def get_all_thresholds(self) -> Dict[tuple[str, str], PerformanceThreshold]:
        """
        Get all configured thresholds.

        Returns:
            Dictionary mapping (workflow_type, dataset_size_category) to threshold

        Examples:
            >>> config = OptimizationConfig.create_default()
            >>> thresholds = config.get_all_thresholds()
            >>> print(f"Configured: {len(thresholds)} threshold combinations")
            Configured: 5 threshold combinations
        """
        return self.thresholds.copy()


# Module-level default configuration (lazy initialization)
_default_config: Optional[OptimizationConfig] = None


def get_default_config() -> OptimizationConfig:
    """
    Get the default optimization configuration (singleton).

    This creates a single shared configuration instance on first call,
    then returns the same instance for subsequent calls.

    Returns:
        OptimizationConfig with default settings

    Examples:
        >>> config = get_default_config()
        >>> threshold = config.get_threshold('grid_search')
        >>> print(threshold.min_improvement_percent)
        5.0
    """
    global _default_config
    if _default_config is None:
        _default_config = OptimizationConfig.create_default()
    return _default_config


def set_default_config(config: OptimizationConfig) -> None:
    """
    Set the default optimization configuration globally.

    Args:
        config: OptimizationConfig to use as default

    Examples:
        >>> strict_config = OptimizationConfig.create_strict()
        >>> set_default_config(strict_config)
        >>> # Now all code using get_default_config() will use strict settings
    """
    global _default_config
    _default_config = config
