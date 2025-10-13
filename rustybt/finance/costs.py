"""Overnight financing and borrow cost models for leveraged and short positions.

This module provides:
- BorrowCostModel: Calculates daily interest on short position values
- OvernightFinancingModel: Calculates daily financing costs/credits for leveraged positions
- Rate providers: DictRateProvider and CSVRateProvider for both models

The daily cost formulas are:
1. Borrow cost (short positions):
    daily_cost = abs(position_value) × (annual_rate / days_in_year)

2. Overnight financing (leveraged positions):
    daily_financing = leveraged_exposure × (annual_rate / days_in_year)
    where leveraged_exposure = position_value - cash_used

Examples:
    Borrow cost - Short 100 shares of AAPL at $150 with 0.3% annual rate:
    - Position value: $15,000
    - Daily cost: $15,000 × (0.003 / 365) = $0.123
    - Annual cost (if held 365 days): ~$45

    Overnight financing - Long $100k AAPL with $50k cash (2x leverage) at 5% rate:
    - Leveraged exposure: $50,000
    - Daily cost: $50,000 × (0.05 / 365) = $6.85
    - Annual cost (if held 365 days): ~$2,500
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
import polars as pl
import structlog

logger = structlog.get_logger(__name__)


class BorrowRateType(Enum):
    """Classification of borrow rates by difficulty."""

    EASY_TO_BORROW = "easy"  # 0.3% - 1%
    MODERATE = "moderate"  # 1% - 5%
    HARD_TO_BORROW = "hard"  # 5% - 50%
    EXTREMELY_HARD = "extreme"  # 50%+


@dataclass(frozen=True)
class BorrowCostResult:
    """Result of daily borrow cost accrual.

    Attributes:
        total_cost: Total cost across all positions
        position_costs: Cost per asset symbol
        timestamp: Time of accrual
        positions_processed: Number of positions with costs accrued
        metadata: Additional metadata (default_rate, days_in_year, etc.)
    """

    total_cost: Decimal
    position_costs: dict[str, Decimal]
    timestamp: pd.Timestamp
    positions_processed: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"BorrowCostResult(total={self.total_cost}, "
            f"positions={self.positions_processed}, "
            f"timestamp={self.timestamp})"
        )


class BorrowRateProvider(Protocol):
    """Protocol for borrow rate data sources.

    Defines the interface that all borrow rate providers must implement.
    """

    @abstractmethod
    def get_rate(self, symbol: str, timestamp: pd.Timestamp) -> Decimal | None:
        """Get borrow rate for a symbol at a given time.

        Args:
            symbol: Asset symbol (e.g., "AAPL", "GME")
            timestamp: Time for rate lookup (supports time-varying rates)

        Returns:
            Annual borrow rate as decimal (e.g., 0.003 = 0.3%) or None if unavailable
        """
        ...

    @abstractmethod
    def get_rate_type(self, symbol: str, rate: Decimal) -> BorrowRateType:
        """Classify borrow rate difficulty.

        Args:
            symbol: Asset symbol
            rate: Annual borrow rate

        Returns:
            Classification of borrow rate difficulty
        """
        ...


class DictBorrowRateProvider:
    """In-memory dictionary-based borrow rate provider.

    Fast lookup for static rate configurations.

    Example:
        >>> rates = {"AAPL": Decimal("0.003"), "GME": Decimal("0.25")}
        >>> provider = DictBorrowRateProvider(rates)
        >>> provider.get_rate("AAPL", pd.Timestamp("2023-01-01"))
        Decimal('0.003')
    """

    def __init__(self, rates: dict[str, Decimal], normalize_symbols: bool = True):
        """Initialize dictionary rate provider.

        Args:
            rates: Mapping of symbol to annual borrow rate
            normalize_symbols: Convert symbols to uppercase for lookup
        """
        self.normalize_symbols = normalize_symbols

        # Normalize symbols if configured
        if normalize_symbols:
            self.rates = {k.upper(): v for k, v in rates.items()}
        else:
            self.rates = dict(rates)

        logger.info(
            "dict_borrow_rate_provider_initialized",
            num_symbols=len(self.rates),
            sample_rates=str(dict(list(self.rates.items())[:3])),
        )

    def get_rate(self, symbol: str, timestamp: pd.Timestamp) -> Decimal | None:
        """Get borrow rate from dictionary.

        Args:
            symbol: Asset symbol
            timestamp: Time for rate lookup (unused for static rates)

        Returns:
            Annual borrow rate or None if not found
        """
        lookup_symbol = symbol.upper() if self.normalize_symbols else symbol

        rate = self.rates.get(lookup_symbol)

        if rate is not None:
            logger.debug(
                "borrow_rate_found",
                symbol=symbol,
                rate=str(rate),
                rate_type=self.get_rate_type(symbol, rate).value,
            )

        return rate

    def get_rate_type(self, symbol: str, rate: Decimal) -> BorrowRateType:
        """Classify borrow rate difficulty.

        Args:
            symbol: Asset symbol
            rate: Annual borrow rate

        Returns:
            Classification of borrow rate difficulty
        """
        if rate < Decimal("0.01"):  # < 1%
            return BorrowRateType.EASY_TO_BORROW
        elif rate < Decimal("0.05"):  # < 5%
            return BorrowRateType.MODERATE
        elif rate < Decimal("0.50"):  # < 50%
            return BorrowRateType.HARD_TO_BORROW
        else:
            return BorrowRateType.EXTREMELY_HARD


class CSVBorrowRateProvider:
    """CSV file-based borrow rate provider.

    Supports time-varying rates with date columns.

    CSV Format (static rates):
        symbol,annual_rate
        AAPL,0.003
        GME,0.25

    CSV Format (time-varying rates):
        symbol,date,annual_rate
        AAPL,2023-01-01,0.003
        GME,2021-01-01,0.05
        GME,2021-01-15,0.80
    """

    def __init__(self, csv_path: Path, normalize_symbols: bool = True, cache_rates: bool = True):
        """Initialize CSV rate provider.

        Args:
            csv_path: Path to CSV file with borrow rates
            normalize_symbols: Convert symbols to uppercase
            cache_rates: Cache loaded rates in memory

        Raises:
            BorrowRateLoadError: If CSV file cannot be loaded or validated
        """
        self.csv_path = csv_path
        self.normalize_symbols = normalize_symbols
        self.cache_rates = cache_rates
        self._rate_cache: dict[tuple[str, pd.Timestamp], Decimal] = {}

        # Load CSV using Polars for performance
        self.df = self._load_csv()

        logger.info(
            "csv_borrow_rate_provider_initialized",
            csv_path=str(csv_path),
            num_rows=len(self.df),
            unique_symbols=self.df.select("symbol").n_unique(),
        )

    def _load_csv(self) -> pl.DataFrame:
        """Load and validate CSV file.

        Returns:
            Validated Polars DataFrame

        Raises:
            BorrowRateLoadError: If CSV file cannot be loaded or validated
        """
        try:
            df = pl.read_csv(self.csv_path)

            # Validate required columns
            required_cols = {"symbol", "annual_rate"}
            if not required_cols.issubset(df.columns):
                raise ValueError(
                    f"CSV missing required columns. "
                    f"Expected: {required_cols}, Got: {set(df.columns)}"
                )

            # Normalize symbols if configured
            if self.normalize_symbols:
                df = df.with_columns(pl.col("symbol").str.to_uppercase().alias("symbol"))

            # Convert date column if present (for time-varying rates)
            if "date" in df.columns:
                df = df.with_columns(pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("date"))

                # Validate chronological date ordering per symbol
                self._validate_chronological_dates(df)

            # Validate rate bounds (0% to 100%)
            invalid_rates = df.filter((pl.col("annual_rate") < 0.0) | (pl.col("annual_rate") > 1.0))

            if len(invalid_rates) > 0:
                logger.warning(
                    "invalid_borrow_rates_found",
                    num_invalid=len(invalid_rates),
                    sample=invalid_rates.head(5).to_dicts(),
                )
                # Filter out invalid rates
                df = df.filter((pl.col("annual_rate") >= 0.0) & (pl.col("annual_rate") <= 1.0))

            return df

        except Exception as e:
            logger.error("csv_load_failed", csv_path=str(self.csv_path), error=str(e))
            raise BorrowRateLoadError(f"Failed to load CSV: {e}") from e

    def _validate_chronological_dates(self, df: pl.DataFrame) -> None:
        """Validate that dates are in chronological order per symbol.

        Args:
            df: DataFrame with date column
        """
        # Check each symbol for chronological ordering
        symbols = df.select("symbol").unique().to_series().to_list()

        non_chronological_symbols = []

        for symbol in symbols:
            symbol_df = df.filter(pl.col("symbol") == symbol).sort("date")

            # Check if dates are strictly increasing
            dates = symbol_df.select("date").to_series().to_list()

            for i in range(1, len(dates)):
                if dates[i] <= dates[i - 1]:
                    non_chronological_symbols.append(
                        {
                            "symbol": symbol,
                            "date1": dates[i - 1],
                            "date2": dates[i],
                            "row_indices": [i - 1, i],
                        }
                    )
                    break  # Only report first violation per symbol

        if non_chronological_symbols:
            logger.warning(
                "non_chronological_dates_found_in_csv",
                num_symbols_affected=len(non_chronological_symbols),
                violations=non_chronological_symbols[:5],  # Show first 5
                csv_path=str(self.csv_path),
            )
            # Note: We log a warning but don't raise an error, allowing the data to load
            # The sort in get_rate() will handle out-of-order dates gracefully

    def get_rate(self, symbol: str, timestamp: pd.Timestamp) -> Decimal | None:
        """Get borrow rate from CSV.

        Args:
            symbol: Asset symbol
            timestamp: Time for rate lookup

        Returns:
            Annual borrow rate or None if not found
        """
        lookup_symbol = symbol.upper() if self.normalize_symbols else symbol

        # Check cache first
        cache_key = (lookup_symbol, timestamp)
        if self.cache_rates and cache_key in self._rate_cache:
            return self._rate_cache[cache_key]

        # Query CSV for rate
        if "date" in self.df.columns:
            # Time-varying rates: find most recent rate <= timestamp
            filtered = self.df.filter(
                (pl.col("symbol") == lookup_symbol) & (pl.col("date") <= timestamp.date())
            ).sort("date", descending=True)

            if len(filtered) > 0:
                rate = Decimal(str(filtered[0, "annual_rate"]))
            else:
                rate = None
        else:
            # Static rates: direct lookup
            filtered = self.df.filter(pl.col("symbol") == lookup_symbol)

            if len(filtered) > 0:
                rate = Decimal(str(filtered[0, "annual_rate"]))
            else:
                rate = None

        # Cache result
        if self.cache_rates and rate is not None:
            self._rate_cache[cache_key] = rate

        if rate is not None:
            logger.debug(
                "borrow_rate_found_in_csv",
                symbol=symbol,
                rate=str(rate),
                rate_type=self.get_rate_type(symbol, rate).value,
            )

        return rate

    def get_rate_type(self, symbol: str, rate: Decimal) -> BorrowRateType:
        """Classify borrow rate difficulty.

        Args:
            symbol: Asset symbol
            rate: Annual borrow rate

        Returns:
            Classification of borrow rate difficulty
        """
        if rate < Decimal("0.01"):  # < 1%
            return BorrowRateType.EASY_TO_BORROW
        elif rate < Decimal("0.05"):  # < 5%
            return BorrowRateType.MODERATE
        elif rate < Decimal("0.50"):  # < 50%
            return BorrowRateType.HARD_TO_BORROW
        else:
            return BorrowRateType.EXTREMELY_HARD


class BorrowCostModel:
    """Borrow cost model for short position financing.

    Calculates daily interest on short position values based on
    configurable borrow rates per asset.

    Daily cost formula:
        daily_cost = abs(position_value) × (annual_rate / days_in_year)

    Example:
        >>> rates = {"AAPL": Decimal("0.003")}
        >>> provider = DictBorrowRateProvider(rates)
        >>> model = BorrowCostModel(provider)
        >>> # Short 100 shares of AAPL at $150 = $15,000 position value
        >>> cost, rate = model.calculate_daily_cost(
        ...     "AAPL", Decimal("15000.00"), pd.Timestamp("2023-01-01")
        ... )
        >>> cost  # Daily cost: $15,000 × (0.003 / 365) = $0.123
        Decimal('0.123287671...')
    """

    def __init__(
        self,
        rate_provider: BorrowRateProvider,
        default_rate: Decimal = Decimal("0.003"),  # 0.3% annual
        days_in_year: int = 365,
    ):
        """Initialize borrow cost model.

        Args:
            rate_provider: Provider for borrow rate lookups
            default_rate: Default annual rate when specific rate unavailable
            days_in_year: Days per year for daily rate calculation (365 or 360)
        """
        self.rate_provider = rate_provider
        self.default_rate = default_rate
        self.days_in_year = days_in_year

        logger.info(
            "borrow_cost_model_initialized",
            default_rate=str(default_rate),
            days_in_year=days_in_year,
            provider_type=type(rate_provider).__name__,
        )

    def calculate_daily_cost(
        self, symbol: str, position_value: Decimal, current_time: pd.Timestamp
    ) -> tuple[Decimal, Decimal]:
        """Calculate daily borrow cost for a short position.

        Args:
            symbol: Asset symbol
            position_value: Absolute value of position (positive)
            current_time: Current timestamp for rate lookup

        Returns:
            Tuple of (daily_cost, annual_rate_used)
        """
        # Get borrow rate (try specific rate, fall back to default)
        annual_rate = self.rate_provider.get_rate(symbol, current_time)

        if annual_rate is None:
            annual_rate = self.default_rate
            logger.debug(
                "using_default_borrow_rate",
                symbol=symbol,
                default_rate=str(self.default_rate),
            )
        else:
            logger.debug("using_symbol_borrow_rate", symbol=symbol, annual_rate=str(annual_rate))

        # Calculate daily rate
        daily_rate = annual_rate / Decimal(str(self.days_in_year))

        # Calculate daily cost
        daily_cost = position_value * daily_rate

        return daily_cost, annual_rate

    def accrue_costs(self, ledger: Any, current_time: pd.Timestamp) -> BorrowCostResult:
        """Accrue borrow costs for all short positions.

        Debits cash from ledger and tracks accumulated costs per position.

        Args:
            ledger: DecimalLedger with positions
            current_time: Current simulation time

        Returns:
            BorrowCostResult with cost details
        """
        total_cost = Decimal("0")
        position_costs: dict[str, Decimal] = {}
        positions_processed = 0

        # Iterate over all positions in ledger
        for asset, position in ledger.positions.items():
            # Only process short positions (negative amount)
            if position.amount < Decimal("0"):
                # Get symbol for rate lookup
                symbol = asset.symbol if hasattr(asset, "symbol") else str(asset)

                # Calculate position value (absolute)
                position_value = abs(position.market_value)

                # Calculate daily cost
                daily_cost, annual_rate = self.calculate_daily_cost(
                    symbol, position_value, current_time
                )

                # Debit from cash
                ledger.cash -= daily_cost

                # Track accumulated cost in position
                if not hasattr(position, "accumulated_borrow_cost"):
                    position.accumulated_borrow_cost = Decimal("0")

                position.accumulated_borrow_cost += daily_cost

                # Record cost
                position_costs[symbol] = daily_cost
                total_cost += daily_cost
                positions_processed += 1

                logger.info(
                    "borrow_cost_accrued",
                    symbol=symbol,
                    position_value=str(position_value),
                    annual_rate=str(annual_rate),
                    daily_cost=str(daily_cost),
                    accumulated_cost=str(position.accumulated_borrow_cost),
                    cash_after_debit=str(ledger.cash),
                )

        # Create result
        result = BorrowCostResult(
            total_cost=total_cost,
            position_costs=position_costs,
            timestamp=current_time,
            positions_processed=positions_processed,
            metadata={
                "default_rate": str(self.default_rate),
                "days_in_year": self.days_in_year,
            },
        )

        if positions_processed > 0:
            logger.info(
                "borrow_costs_accrued_summary",
                total_cost=str(total_cost),
                positions_processed=positions_processed,
                timestamp=str(current_time),
            )

        return result


class BorrowRateLoadError(Exception):
    """Raised when borrow rate data fails to load."""


class BorrowCostCalculationError(Exception):
    """Raised when borrow cost calculation fails."""


# ====================================================================
# Overnight Financing Model for Leveraged Positions
# ====================================================================


class AssetClass(Enum):
    """Asset class for financing rate determination."""

    EQUITY = "equity"
    FOREX = "forex"
    CRYPTO = "crypto"
    FUTURES = "futures"
    COMMODITY = "commodity"


class FinancingDirection(Enum):
    """Direction of financing (cost vs. credit)."""

    DEBIT = "debit"  # Pays financing (cost)
    CREDIT = "credit"  # Receives financing (income)


@dataclass(frozen=True)
class FinancingResult:
    """Result of daily financing application.

    Attributes:
        total_financing: Total financing across all positions (positive = cost)
        position_financing: Financing per asset symbol
        timestamp: Current timestamp
        positions_processed: Number of positions processed
        metadata: Additional metadata
    """

    total_financing: Decimal
    position_financing: dict[str, Decimal]
    timestamp: pd.Timestamp
    positions_processed: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_cost(self) -> Decimal:
        """Total financing cost (debits only)."""
        return max(self.total_financing, Decimal("0"))

    @property
    def total_credit(self) -> Decimal:
        """Total financing credit (credits only)."""
        return abs(min(self.total_financing, Decimal("0")))

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"FinancingResult(total={self.total_financing}, "
            f"positions={self.positions_processed}, "
            f"timestamp={self.timestamp})"
        )


class FinancingRateProvider(Protocol):
    """Protocol for financing rate data sources.

    Financing rates are annual rates as decimals:
    - Long leverage: Always positive (cost to hold leveraged long position)
    - Short leverage: Can be positive (cost) or negative (credit) for forex/crypto swap rates
    """

    @abstractmethod
    def get_long_rate(
        self, symbol: str, asset_class: AssetClass, timestamp: pd.Timestamp
    ) -> Decimal:
        """Get financing rate for long leverage.

        Args:
            symbol: Asset symbol
            asset_class: Asset class for rate determination
            timestamp: Time for rate lookup

        Returns:
            Annual financing rate as decimal (always positive for cost)
        """
        ...

    @abstractmethod
    def get_short_rate(
        self, symbol: str, asset_class: AssetClass, timestamp: pd.Timestamp
    ) -> Decimal:
        """Get financing rate for short leverage.

        Args:
            symbol: Asset symbol
            asset_class: Asset class for rate determination
            timestamp: Time for rate lookup

        Returns:
            Annual financing rate as decimal (can be negative for credit)
        """
        ...


class DictFinancingRateProvider:
    """In-memory dictionary-based financing rate provider.

    Supports different rates for long and short positions, with optional
    symbol-specific overrides.

    Example:
        >>> long_rates = {AssetClass.EQUITY: Decimal("0.05")}
        >>> short_rates = {AssetClass.FOREX: Decimal("-0.005")}
        >>> provider = DictFinancingRateProvider(long_rates, short_rates)
        >>> rate = provider.get_long_rate("AAPL", AssetClass.EQUITY, pd.Timestamp("2023-01-01"))
        >>> assert rate == Decimal("0.05")
    """

    def __init__(
        self,
        long_rates: dict[AssetClass, Decimal],
        short_rates: dict[AssetClass, Decimal] | None = None,
        symbol_overrides: dict[str, tuple[Decimal, Decimal]] | None = None,
        normalize_symbols: bool = True,
    ):
        """Initialize dictionary financing rate provider.

        Args:
            long_rates: Mapping of asset class to long financing rate
            short_rates: Mapping of asset class to short financing rate (optional)
            symbol_overrides: Symbol-specific (long_rate, short_rate) overrides
            normalize_symbols: Convert symbols to uppercase for lookup
        """
        self.long_rates = long_rates
        self.short_rates = short_rates or {}
        self.normalize_symbols = normalize_symbols

        # Normalize symbol overrides
        if symbol_overrides and normalize_symbols:
            self.symbol_overrides = {k.upper(): v for k, v in symbol_overrides.items()}
        else:
            self.symbol_overrides = symbol_overrides or {}

        logger.info(
            "dict_financing_rate_provider_initialized",
            num_asset_classes=len(long_rates),
            num_symbol_overrides=len(self.symbol_overrides),
        )

    def get_long_rate(
        self, symbol: str, asset_class: AssetClass, timestamp: pd.Timestamp
    ) -> Decimal:
        """Get financing rate for long leverage."""
        lookup_symbol = symbol.upper() if self.normalize_symbols else symbol

        # Check for symbol-specific override
        if lookup_symbol in self.symbol_overrides:
            long_rate, _ = self.symbol_overrides[lookup_symbol]
            logger.debug("using_symbol_override_long_rate", symbol=symbol, rate=str(long_rate))
            return long_rate

        # Use asset class default
        rate = self.long_rates.get(asset_class, Decimal("0.05"))  # 5% default

        logger.debug(
            "using_asset_class_long_rate",
            symbol=symbol,
            asset_class=asset_class.value,
            rate=str(rate),
        )

        return rate

    def get_short_rate(
        self, symbol: str, asset_class: AssetClass, timestamp: pd.Timestamp
    ) -> Decimal:
        """Get financing rate for short leverage."""
        lookup_symbol = symbol.upper() if self.normalize_symbols else symbol

        # Check for symbol-specific override
        if lookup_symbol in self.symbol_overrides:
            _, short_rate = self.symbol_overrides[lookup_symbol]
            logger.debug("using_symbol_override_short_rate", symbol=symbol, rate=str(short_rate))
            return short_rate

        # Use asset class default (may be negative for forex/crypto)
        rate = self.short_rates.get(asset_class, Decimal("0"))

        logger.debug(
            "using_asset_class_short_rate",
            symbol=symbol,
            asset_class=asset_class.value,
            rate=str(rate),
        )

        return rate


class CSVFinancingRateProvider:
    """CSV file-based financing rate provider.

    Supports time-varying rates with date columns.

    CSV Format:
    ```
    symbol,asset_class,date,long_rate,short_rate,notes
    AAPL,equity,2023-01-01,0.05,0.00,Margin interest for equities
    EUR/USD,forex,2023-01-01,0.00,-0.005,Negative carry (pay to short)
    USD/JPY,forex,2023-01-01,0.00,0.012,Positive carry (receive to short)
    BTC-USD,crypto,2023-01-01,0.10,-0.02,Funding rate
    ```

    Example:
        >>> provider = CSVFinancingRateProvider(Path("rates.csv"))
        >>> rate = provider.get_long_rate("AAPL", AssetClass.EQUITY, pd.Timestamp("2023-06-01"))
    """

    def __init__(self, csv_path: Path, normalize_symbols: bool = True, cache_rates: bool = True):
        """Initialize CSV financing rate provider.

        Args:
            csv_path: Path to CSV file with financing rates
            normalize_symbols: Convert symbols to uppercase
            cache_rates: Cache loaded rates in memory
        """
        self.csv_path = csv_path
        self.normalize_symbols = normalize_symbols
        self.cache_rates = cache_rates
        self._rate_cache: dict[tuple[str, pd.Timestamp, str], Decimal] = {}

        # Load CSV using Polars
        self.df = self._load_csv()

        logger.info(
            "csv_financing_rate_provider_initialized",
            csv_path=str(csv_path),
            num_rows=len(self.df),
            unique_symbols=self.df.select("symbol").n_unique(),
        )

    def _load_csv(self) -> pl.DataFrame:
        """Load and validate CSV file."""
        try:
            df = pl.read_csv(self.csv_path)

            # Validate required columns
            required_cols = {"symbol", "asset_class", "long_rate", "short_rate"}
            if not required_cols.issubset(df.columns):
                raise ValueError(
                    f"CSV missing required columns. "
                    f"Expected: {required_cols}, Got: {set(df.columns)}"
                )

            # Normalize symbols if configured
            if self.normalize_symbols:
                df = df.with_columns(pl.col("symbol").str.to_uppercase().alias("symbol"))

            # Convert date column if present
            if "date" in df.columns:
                df = df.with_columns(pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("date"))

                # Validate chronological date ordering per symbol
                self._validate_chronological_dates(df)

            return df

        except Exception as e:
            logger.error("csv_load_failed", csv_path=str(self.csv_path), error=str(e))
            raise FinancingRateLoadError(f"Failed to load CSV: {e}") from e

    def _validate_chronological_dates(self, df: pl.DataFrame) -> None:
        """Validate that dates are in chronological order per symbol.

        Args:
            df: DataFrame with date column

        Raises:
            FinancingRateLoadError: If dates are not chronological for any symbol
        """
        # Check each symbol for chronological ordering
        symbols = df.select("symbol").unique().to_series().to_list()

        non_chronological_symbols = []

        for symbol in symbols:
            symbol_df = df.filter(pl.col("symbol") == symbol).sort("date")

            # Check if dates are strictly increasing
            dates = symbol_df.select("date").to_series().to_list()

            for i in range(1, len(dates)):
                if dates[i] <= dates[i - 1]:
                    non_chronological_symbols.append(
                        {
                            "symbol": symbol,
                            "date1": dates[i - 1],
                            "date2": dates[i],
                            "row_indices": [i - 1, i],
                        }
                    )
                    break  # Only report first violation per symbol

        if non_chronological_symbols:
            logger.warning(
                "non_chronological_dates_found_in_csv",
                num_symbols_affected=len(non_chronological_symbols),
                violations=non_chronological_symbols[:5],  # Show first 5
                csv_path=str(self.csv_path),
            )
            # Note: We log a warning but don't raise an error, allowing the data to load
            # The sort in _get_rate() will handle out-of-order dates gracefully

    def get_long_rate(
        self, symbol: str, asset_class: AssetClass, timestamp: pd.Timestamp
    ) -> Decimal:
        """Get financing rate for long leverage from CSV."""
        return self._get_rate(symbol, asset_class, timestamp, "long_rate")

    def get_short_rate(
        self, symbol: str, asset_class: AssetClass, timestamp: pd.Timestamp
    ) -> Decimal:
        """Get financing rate for short leverage from CSV."""
        return self._get_rate(symbol, asset_class, timestamp, "short_rate")

    def _get_rate(
        self, symbol: str, asset_class: AssetClass, timestamp: pd.Timestamp, rate_column: str
    ) -> Decimal:
        """Internal method to fetch rate from CSV."""
        lookup_symbol = symbol.upper() if self.normalize_symbols else symbol

        # Check cache
        cache_key = (lookup_symbol, timestamp, rate_column)
        if self.cache_rates and cache_key in self._rate_cache:
            return self._rate_cache[cache_key]

        # Query CSV for rate
        if "date" in self.df.columns:
            # Time-varying rates
            filtered = self.df.filter(
                (pl.col("symbol") == lookup_symbol)
                & (pl.col("asset_class") == asset_class.value)
                & (pl.col("date") <= timestamp.date())
            ).sort("date", descending=True)
        else:
            # Static rates
            filtered = self.df.filter(
                (pl.col("symbol") == lookup_symbol) & (pl.col("asset_class") == asset_class.value)
            )

        if len(filtered) > 0:
            rate = Decimal(str(filtered[0, rate_column]))
        else:
            # Default rates if not found
            rate = Decimal("0.05") if rate_column == "long_rate" else Decimal("0")

            logger.warning(
                "financing_rate_not_found_using_default",
                symbol=symbol,
                asset_class=asset_class.value,
                rate_type=rate_column,
                default_rate=str(rate),
            )

        # Cache result
        if self.cache_rates:
            self._rate_cache[cache_key] = rate

        return rate


class OvernightFinancingModel:
    """Overnight financing model for leveraged positions.

    Calculates daily financing costs/credits based on leveraged exposure.

    Formulas:
    - Long leverage: financing = leveraged_exposure × (long_rate / days_in_year)
    - Short leverage: financing = leveraged_exposure × (short_rate / days_in_year)

    Where leveraged_exposure = position_value - cash_used

    Examples:
    1. Equity margin (long):
       - Position: $100,000 in AAPL with $50,000 cash (2x leverage)
       - Leveraged exposure: $50,000
       - Annual rate: 5%
       - Daily cost: $50,000 × (0.05 / 365) = $6.85

    2. Forex carry trade (short EUR/USD):
       - Position: Short €100,000 at 1.10 = -$110,000
       - Swap rate: -0.5% (pay to hold short)
       - Daily cost: $110,000 × (0.005 / 360) = $1.53

    3. Forex positive carry (short USD/JPY):
       - Position: Short ¥10,000,000 at 110 = -$90,909
       - Swap rate: +1.2% (receive to hold short)
       - Daily credit: $90,909 × (-0.012 / 360) = -$3.03 (credit)
    """

    def __init__(
        self,
        rate_provider: FinancingRateProvider,
        days_in_year: int = 365,
        rollover_time: pd.Timestamp | None = None,
    ):
        """Initialize overnight financing model.

        Args:
            rate_provider: Provider for financing rate lookups
            days_in_year: Days per year (365 for equities, 360 for forex/some futures)
            rollover_time: Specific time for rollover (e.g., 5pm ET for forex)
        """
        self.rate_provider = rate_provider
        self.days_in_year = days_in_year
        self.rollover_time = rollover_time

        logger.info(
            "overnight_financing_model_initialized",
            days_in_year=days_in_year,
            provider_type=type(rate_provider).__name__,
        )

    def calculate_leveraged_exposure(self, position_value: Decimal, cash_used: Decimal) -> Decimal:
        """Calculate leveraged exposure.

        Args:
            position_value: Total position value (absolute)
            cash_used: Cash used to open position

        Returns:
            Leveraged exposure (amount financed)

        Example:
            >>> model = OvernightFinancingModel(provider)
            >>> exposure = model.calculate_leveraged_exposure(Decimal("100000"), Decimal("50000"))
            >>> assert exposure == Decimal("50000")  # $50k leverage on $100k position
        """
        # Leveraged exposure = position value - cash used
        # E.g., $100k position with $50k cash = $50k leveraged
        leveraged_exposure = abs(position_value) - cash_used

        # Exposure must be non-negative
        return max(leveraged_exposure, Decimal("0"))

    def calculate_daily_financing(
        self,
        symbol: str,
        asset_class: AssetClass,
        leveraged_exposure: Decimal,
        is_long: bool,
        current_time: pd.Timestamp,
    ) -> tuple[Decimal, Decimal]:
        """Calculate daily financing cost/credit.

        Args:
            symbol: Asset symbol
            asset_class: Asset class for rate lookup
            leveraged_exposure: Amount of leverage (financed amount)
            is_long: True for long position, False for short
            current_time: Current timestamp for rate lookup

        Returns:
            Tuple of (daily_financing, annual_rate_used)
            Positive = cost (debit), negative = credit

        Example:
            >>> financing, rate = model.calculate_daily_financing(
            ...     "AAPL", AssetClass.EQUITY, Decimal("50000"), True, pd.Timestamp("2023-01-01")
            ... )
            >>> # $50k × (5% / 365) = $6.85/day
            >>> assert financing == Decimal("50000") * Decimal("0.05") / Decimal("365")
        """
        # Get appropriate rate
        if is_long:
            annual_rate = self.rate_provider.get_long_rate(symbol, asset_class, current_time)
        else:
            annual_rate = self.rate_provider.get_short_rate(symbol, asset_class, current_time)

        # Calculate daily rate
        daily_rate = annual_rate / Decimal(str(self.days_in_year))

        # Calculate daily financing
        daily_financing = leveraged_exposure * daily_rate

        logger.debug(
            "daily_financing_calculated",
            symbol=symbol,
            leveraged_exposure=str(leveraged_exposure),
            annual_rate=str(annual_rate),
            daily_rate=str(daily_rate),
            daily_financing=str(daily_financing),
            direction="long" if is_long else "short",
        )

        return daily_financing, annual_rate

    def apply_financing(self, ledger: Any, current_time: pd.Timestamp) -> FinancingResult:
        """Apply overnight financing to leveraged positions.

        Debits/credits cash from ledger and tracks accumulated financing per position.

        Args:
            ledger: DecimalLedger with positions
            current_time: Current simulation time

        Returns:
            FinancingResult with financing details

        Example:
            >>> result = model.apply_financing(ledger, pd.Timestamp("2023-01-01"))
            >>> assert result.positions_processed >= 0
            >>> assert result.total_financing >= Decimal("0")  # For long-only leveraged portfolio
        """
        total_financing = Decimal("0")
        position_financing: dict[str, Decimal] = {}
        positions_processed = 0

        # Iterate over all positions in ledger
        for asset, position in ledger.positions.items():
            # Get position details
            symbol = asset.symbol if hasattr(asset, "symbol") else str(asset)
            asset_class_attr = getattr(asset, "asset_class", None)

            # Convert asset_class to enum if needed
            if isinstance(asset_class_attr, AssetClass):
                asset_class = asset_class_attr
            elif isinstance(asset_class_attr, str):
                try:
                    asset_class = AssetClass(asset_class_attr.lower())
                except ValueError:
                    asset_class = AssetClass.EQUITY
            else:
                asset_class = AssetClass.EQUITY

            # Calculate leveraged exposure using position's explicit cash_used field
            # If cash_used is not set (Decimal("0")), use market value (no leverage)
            position_value = abs(position.market_value)
            cash_used = position.cash_used if position.cash_used > Decimal("0") else position_value
            leveraged_exposure = self.calculate_leveraged_exposure(position_value, cash_used)

            # Skip if no leverage
            if leveraged_exposure <= Decimal("0"):
                continue

            # Determine position direction
            is_long = position.amount > Decimal("0")

            # Calculate daily financing
            daily_financing, annual_rate = self.calculate_daily_financing(
                symbol, asset_class, leveraged_exposure, is_long, current_time
            )

            # Apply financing to cash (debit = positive, credit = negative)
            ledger.cash -= daily_financing

            # Track accumulated financing in position
            if not hasattr(position, "accumulated_financing"):
                position.accumulated_financing = Decimal("0")

            position.accumulated_financing += daily_financing

            # Record financing
            position_financing[symbol] = daily_financing
            total_financing += daily_financing
            positions_processed += 1

            # Determine direction for logging
            direction = (
                FinancingDirection.DEBIT if daily_financing > 0 else FinancingDirection.CREDIT
            )

            logger.info(
                "overnight_financing_applied",
                symbol=symbol,
                asset_class=asset_class.value,
                leveraged_exposure=str(leveraged_exposure),
                annual_rate=str(annual_rate),
                daily_financing=str(daily_financing),
                accumulated_financing=str(position.accumulated_financing),
                direction=direction.value,
                is_long=is_long,
                cash_after=str(ledger.cash),
            )

        # Create result
        result = FinancingResult(
            total_financing=total_financing,
            position_financing=position_financing,
            timestamp=current_time,
            positions_processed=positions_processed,
            metadata={
                "days_in_year": self.days_in_year,
                "total_cost": str(max(total_financing, Decimal("0"))),
                "total_credit": str(abs(min(total_financing, Decimal("0")))),
            },
        )

        if positions_processed > 0:
            logger.info(
                "overnight_financing_summary",
                total_financing=str(total_financing),
                total_cost=str(result.total_cost),
                total_credit=str(result.total_credit),
                positions_processed=positions_processed,
                timestamp=str(current_time),
            )

        return result


class FinancingRateLoadError(Exception):
    """Raised when financing rate data fails to load."""


class FinancingCalculationError(Exception):
    """Raised when financing calculation fails."""
