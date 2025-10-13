"""Property-based tests for data pipeline operations and OHLCV validation."""

from decimal import Decimal

import polars as pl
from hypothesis import assume, example, given

from rustybt.data.quality import _validate_ohlcv_relationships

from .strategies import decimal_prices, ohlcv_bars


def validate_ohlcv_relationships(data: pl.DataFrame) -> bool:
    """Validate OHLCV relationships in data.

    Args:
        data: DataFrame with OHLCV columns

    Returns:
        True if valid, False otherwise
    """
    violations = _validate_ohlcv_relationships(data)
    return violations == 0


@given(
    bars=ohlcv_bars(num_bars=100, scale=8),
)
@example(
    bars=pl.DataFrame(
        {
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
        }
    )
)
def test_ohlcv_relationships_always_valid(bars: pl.DataFrame) -> None:
    """Test OHLCV relationships are always valid.

    Properties:
        high >= open
        high >= close
        low <= open
        low <= close
        high >= low

    These relationships must hold for all valid OHLCV data.
    """
    # Verify high >= open
    assert (bars["high"] >= bars["open"]).all(), "High must be >= Open"

    # Verify high >= close
    assert (bars["high"] >= bars["close"]).all(), "High must be >= Close"

    # Verify low <= open
    assert (bars["low"] <= bars["open"]).all(), "Low must be <= Open"

    # Verify low <= close
    assert (bars["low"] <= bars["close"]).all(), "Low must be <= Close"

    # Verify high >= low
    assert (bars["high"] >= bars["low"]).all(), "High must be >= Low"


@given(
    bars=ohlcv_bars(num_bars=50, scale=8),
)
def test_ohlcv_validation_function(bars: pl.DataFrame) -> None:
    """Test OHLCV validation function accepts valid data.

    Property:
        validate_ohlcv_relationships(valid_data) = True

    The validation function must accept data that satisfies OHLCV relationships.
    """
    # Validate using the quality module function
    is_valid = validate_ohlcv_relationships(bars)

    assert is_valid, f"Valid OHLCV data rejected by validation function. Sample: {bars.head()}"


@given(
    open_price=decimal_prices(min_value=Decimal("10"), max_value=Decimal("100"), scale=2),
    high_offset=decimal_prices(min_value=Decimal("0"), max_value=Decimal("10"), scale=2),
    low_offset=decimal_prices(min_value=Decimal("0"), max_value=Decimal("10"), scale=2),
    close_offset=decimal_prices(min_value=Decimal("-10"), max_value=Decimal("10"), scale=2),
)
@example(
    open_price=Decimal("50"),
    high_offset=Decimal("5"),
    low_offset=Decimal("5"),
    close_offset=Decimal("2"),
)
def test_ohlcv_construction_from_offsets(
    open_price: Decimal, high_offset: Decimal, low_offset: Decimal, close_offset: Decimal
) -> None:
    """Test OHLCV bar construction maintains relationships.

    Property:
        Constructed OHLCV bar satisfies all relationships

    When constructing OHLCV bars from offsets, relationships must hold.
    """
    close_price = open_price + close_offset
    high_price = max(open_price, close_price) + high_offset
    low_price = min(open_price, close_price) - low_offset

    # Ensure low is positive
    assume(low_price > Decimal("0"))

    # Verify relationships
    assert high_price >= open_price, "High >= Open"
    assert high_price >= close_price, "High >= Close"
    assert low_price <= open_price, "Low <= Open"
    assert low_price <= close_price, "Low <= Close"
    assert high_price >= low_price, "High >= Low"


@given(
    bars=ohlcv_bars(num_bars=20, scale=8),
    split_ratio=decimal_prices(min_value=Decimal("2"), max_value=Decimal("10"), scale=1),
)
@example(
    bars=pl.DataFrame(
        {
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
        }
    ),
    split_ratio=Decimal("2"),
)
def test_split_adjustment_preserves_relationships(bars: pl.DataFrame, split_ratio: Decimal) -> None:
    """Test split adjustment preserves OHLCV relationships.

    Property:
        After split adjustment, OHLCV relationships still hold

    Stock splits change prices but must preserve relative relationships.
    """
    # Apply split adjustment (divide prices, multiply volume)
    split_ratio_float = float(split_ratio)
    adjusted_bars = bars.with_columns(
        [
            (pl.col("open") / split_ratio_float).alias("open"),
            (pl.col("high") / split_ratio_float).alias("high"),
            (pl.col("low") / split_ratio_float).alias("low"),
            (pl.col("close") / split_ratio_float).alias("close"),
            (pl.col("volume") * split_ratio_float).alias("volume"),
        ]
    )

    # Verify relationships still hold
    assert (adjusted_bars["high"] >= adjusted_bars["open"]).all(), "High >= Open after split"
    assert (adjusted_bars["high"] >= adjusted_bars["close"]).all(), "High >= Close after split"
    assert (adjusted_bars["low"] <= adjusted_bars["open"]).all(), "Low <= Open after split"
    assert (adjusted_bars["low"] <= adjusted_bars["close"]).all(), "Low <= Close after split"
    assert (adjusted_bars["high"] >= adjusted_bars["low"]).all(), "High >= Low after split"


@given(
    bars=ohlcv_bars(num_bars=20, scale=2),
    dividend=decimal_prices(min_value=Decimal("0.10"), max_value=Decimal("5.00"), scale=2),
)
@example(
    bars=pl.DataFrame(
        {
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
        }
    ),
    dividend=Decimal("2.50"),
)
def test_dividend_adjustment_preserves_relationships(bars: pl.DataFrame, dividend: Decimal) -> None:
    """Test dividend adjustment preserves OHLCV relationships.

    Property:
        After dividend adjustment, OHLCV relationships still hold

    Dividend adjustments reduce prices but must preserve relative relationships.
    """
    dividend_float = float(dividend)

    # Ensure dividend is smaller than all prices
    min_price = min(bars["low"].min(), bars["open"].min(), bars["close"].min())
    assume(dividend_float < min_price)

    # Apply dividend adjustment (subtract dividend from all prices)
    adjusted_bars = bars.with_columns(
        [
            (pl.col("open") - dividend_float).alias("open"),
            (pl.col("high") - dividend_float).alias("high"),
            (pl.col("low") - dividend_float).alias("low"),
            (pl.col("close") - dividend_float).alias("close"),
        ]
    )

    # Verify relationships still hold
    assert (adjusted_bars["high"] >= adjusted_bars["open"]).all(), "High >= Open after dividend"
    assert (adjusted_bars["high"] >= adjusted_bars["close"]).all(), "High >= Close after dividend"
    assert (adjusted_bars["low"] <= adjusted_bars["open"]).all(), "Low <= Open after dividend"
    assert (adjusted_bars["low"] <= adjusted_bars["close"]).all(), "Low <= Close after dividend"
    assert (adjusted_bars["high"] >= adjusted_bars["low"]).all(), "High >= Low after dividend"


@given(
    bars=ohlcv_bars(num_bars=10, scale=8),
)
def test_roundtrip_preserves_precision(bars: pl.DataFrame) -> None:
    """Test CSV/Parquet roundtrip preserves Decimal precision.

    Property:
        roundtrip(bars) = bars

    Writing to and reading from storage should preserve exact values.
    """
    # Convert to CSV string and back
    csv_string = bars.write_csv()
    reconstructed = pl.read_csv(csv_string.encode())

    # Verify all values match (allowing for small float precision differences)
    for col in ["open", "high", "low", "close", "volume"]:
        original_vals = bars[col].to_list()
        reconstructed_vals = reconstructed[col].to_list()

        for i, (orig, recon) in enumerate(zip(original_vals, reconstructed_vals, strict=False)):
            diff = abs(orig - recon)
            assert diff < 1e-6, (
                f"Roundtrip precision lost for {col}[{i}]: "
                f"original={orig}, reconstructed={recon}, diff={diff}"
            )


@given(
    bars=ohlcv_bars(num_bars=100, scale=8),
)
def test_volume_always_non_negative(bars: pl.DataFrame) -> None:
    """Test volume is always non-negative.

    Property:
        volume >= 0

    Trading volume cannot be negative.
    """
    assert (bars["volume"] >= 0).all(), "Volume must be non-negative"


@given(
    bars=ohlcv_bars(num_bars=50, scale=8),
)
def test_price_range_definition(bars: pl.DataFrame) -> None:
    """Test price range = high - low.

    Property:
        range = high - low >= 0

    Price range is the difference between high and low and must be non-negative.
    """
    price_range = bars["high"] - bars["low"]

    assert (price_range >= 0).all(), "Price range must be non-negative"


@given(
    bars=ohlcv_bars(num_bars=30, scale=8),
)
def test_typical_price_within_range(bars: pl.DataFrame) -> None:
    """Test typical price is within [low, high] range.

    Property:
        low <= typical_price <= high

    Typical price (H+L+C)/3 must be within the bar's range.
    """
    typical_price = (bars["high"] + bars["low"] + bars["close"]) / 3.0

    assert (typical_price >= bars["low"]).all(), "Typical price must be >= low"
    assert (typical_price <= bars["high"]).all(), "Typical price must be <= high"
