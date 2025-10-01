"""Decimal-aware pipeline factors for financial-grade precision.

This module provides Pipeline factors that use Decimal arithmetic instead of
float64 to maintain precision in financial calculations.

Note: This is a proof-of-concept implementation demonstrating Decimal factor
support. Full integration with Pipeline engine requires updates to the
engine's type system and compilation framework.
"""

from decimal import Decimal

import polars as pl
import structlog

logger = structlog.get_logger(__name__)


class DecimalFactor:
    """Base class for Decimal-aware pipeline factors.

    Decimal factors compute values using Decimal arithmetic and return
    Polars Series with Decimal dtype.

    This is a simplified proof-of-concept. Full integration would require
    updates to rustybt.pipeline.engine to support Decimal dtypes in the
    compilation and execution framework.
    """

    def __init__(self, window_length: int = 1):
        """Initialize Decimal factor.

        Args:
            window_length: Number of bars to use in computation
        """
        self.window_length = window_length

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute factor values.

        Args:
            data: Polars DataFrame with OHLCV columns (Decimal dtypes)

        Returns:
            Polars Series with Decimal values

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement compute()")


class DecimalLatestPrice(DecimalFactor):
    """Returns the latest close price as Decimal.

    This factor simply returns the most recent close price for each asset.

    Example:
        >>> factor = DecimalLatestPrice()
        >>> df = pl.DataFrame({
        ...     "date": [date(2023, 1, 1)],
        ...     "sid": [1],
        ...     "close": [Decimal("123.45")],
        ... })
        >>> result = factor.compute(df)
        >>> assert result[0] == Decimal("123.45")
    """

    def __init__(self):
        """Initialize LatestPrice factor (no window needed)."""
        super().__init__(window_length=1)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Return latest close prices.

        Args:
            data: DataFrame with 'close' column (Decimal dtype)

        Returns:
            Series of latest close prices as Decimal
        """
        if "close" not in data.columns:
            raise ValueError("Data must have 'close' column")

        if not isinstance(data["close"].dtype, pl.Decimal):
            raise TypeError("close column must be Decimal dtype")

        # Get last row for each asset (grouped by sid if present)
        if "sid" in data.columns:
            latest = data.group_by("sid").agg(pl.col("close").last())
            return latest["close"]
        else:
            return data["close"].tail(1)


class DecimalSimpleMovingAverage(DecimalFactor):
    """Calculate simple moving average using Decimal arithmetic.

    Uses Polars rolling_mean() on Decimal series to maintain precision.

    Example:
        >>> factor = DecimalSimpleMovingAverage(window_length=3)
        >>> df = pl.DataFrame({
        ...     "close": [Decimal("100"), Decimal("102"), Decimal("104")],
        ... })
        >>> result = factor.compute(df)
        >>> # Mean of 100, 102, 104 = 102
        >>> assert result[-1] == Decimal("102")
    """

    def __init__(self, window_length: int = 20):
        """Initialize SMA factor.

        Args:
            window_length: Number of bars for moving average
        """
        if window_length < 1:
            raise ValueError(f"window_length must be >= 1, got {window_length}")

        super().__init__(window_length=window_length)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Calculate rolling mean of close prices.

        Args:
            data: DataFrame with 'close' column (Decimal dtype)

        Returns:
            Series of SMA values as Decimal
        """
        if "close" not in data.columns:
            raise ValueError("Data must have 'close' column")

        if not isinstance(data["close"].dtype, pl.Decimal):
            raise TypeError("close column must be Decimal dtype")

        # Polars rolling_mean preserves Decimal dtype
        sma = data["close"].rolling_mean(window_size=self.window_length)

        logger.debug(
            "sma_computed",
            window_length=self.window_length,
            num_values=len(sma),
            min_value=str(sma.min()),
            max_value=str(sma.max()),
        )

        return sma


class DecimalReturns(DecimalFactor):
    """Calculate returns using Decimal arithmetic.

    Formula: (close[t] / close[t-window_length]) - 1

    Uses Decimal division to avoid floating-point errors.

    Example:
        >>> factor = DecimalReturns(window_length=1)
        >>> df = pl.DataFrame({
        ...     "close": [Decimal("100"), Decimal("105")],
        ... })
        >>> result = factor.compute(df)
        >>> # (105 / 100) - 1 = 0.05
        >>> assert result[-1] == Decimal("0.05")
    """

    def __init__(self, window_length: int = 1):
        """Initialize Returns factor.

        Args:
            window_length: Number of bars for return calculation
        """
        if window_length < 1:
            raise ValueError(f"window_length must be >= 1, got {window_length}")

        super().__init__(window_length=window_length)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Calculate returns over window.

        Args:
            data: DataFrame with 'close' column (Decimal dtype)

        Returns:
            Series of return values as Decimal
        """
        if "close" not in data.columns:
            raise ValueError("Data must have 'close' column")

        if not isinstance(data["close"].dtype, pl.Decimal):
            raise TypeError("close column must be Decimal dtype")

        if len(data) < self.window_length + 1:
            raise ValueError(
                f"Data length {len(data)} insufficient for window_length "
                f"{self.window_length} (need at least {self.window_length + 1})"
            )

        # Calculate returns: (close[t] / close[t-window_length]) - 1
        # Polars shift operation preserves Decimal dtype
        past_close = data["close"].shift(self.window_length)
        returns = (data["close"] / past_close) - Decimal("1")

        logger.debug(
            "returns_computed",
            window_length=self.window_length,
            num_values=len(returns),
            min_return=str(returns.min()),
            max_return=str(returns.max()),
        )

        return returns


class DecimalAverageDollarVolume(DecimalFactor):
    """Calculate average dollar volume using Decimal arithmetic.

    Formula: mean(close * volume) over window

    Uses Decimal multiplication to maintain precision.

    Example:
        >>> factor = DecimalAverageDollarVolume(window_length=3)
        >>> df = pl.DataFrame({
        ...     "close": [Decimal("100"), Decimal("102"), Decimal("104")],
        ...     "volume": [Decimal("1000"), Decimal("1500"), Decimal("2000")],
        ... })
        >>> result = factor.compute(df)
        >>> # Dollar volumes: 100k, 153k, 208k; mean = 153,666.67
        >>> assert result[-1] > Decimal("150000")
    """

    def __init__(self, window_length: int = 20):
        """Initialize AverageDollarVolume factor.

        Args:
            window_length: Number of bars for moving average
        """
        if window_length < 1:
            raise ValueError(f"window_length must be >= 1, got {window_length}")

        super().__init__(window_length=window_length)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Calculate rolling average of dollar volume.

        Args:
            data: DataFrame with 'close' and 'volume' columns (Decimal dtypes)

        Returns:
            Series of average dollar volume values as Decimal
        """
        if "close" not in data.columns or "volume" not in data.columns:
            raise ValueError("Data must have 'close' and 'volume' columns")

        if not isinstance(data["close"].dtype, pl.Decimal):
            raise TypeError("close column must be Decimal dtype")

        if not isinstance(data["volume"].dtype, pl.Decimal):
            raise TypeError("volume column must be Decimal dtype")

        # Calculate dollar volume: close * volume (Decimal multiplication)
        dollar_volume = data["close"] * data["volume"]

        # Rolling mean preserves Decimal dtype
        avg_dollar_volume = dollar_volume.rolling_mean(window_size=self.window_length)

        logger.debug(
            "avg_dollar_volume_computed",
            window_length=self.window_length,
            num_values=len(avg_dollar_volume),
            min_value=str(avg_dollar_volume.min()),
            max_value=str(avg_dollar_volume.max()),
        )

        return avg_dollar_volume
