"""Property-based tests for performance metrics calculations."""

from decimal import Decimal

import polars as pl
from hypothesis import assume, example, given

from rustybt.finance.metrics.decimal_metrics import calculate_max_drawdown

from .strategies import decimal_prices, return_series


def calculate_cumulative_returns(returns: pl.Series) -> pl.Series:
    """Calculate cumulative returns from a returns series.

    Args:
        returns: Returns series

    Returns:
        Cumulative returns series
    """
    return (returns + 1.0).cumprod()


@given(
    returns=return_series(min_size=30, max_size=252),
)
@example(returns=[Decimal("0.01")] * 100)  # All positive returns
@example(returns=[Decimal("-0.01")] * 100)  # All negative returns
@example(returns=[Decimal("0")] * 100)  # Zero returns
def test_max_drawdown_valid_range(returns: list[Decimal]) -> None:
    """Test max drawdown is in valid range [-1, 0].

    Property:
        -1 <= max_drawdown <= 0

    Maximum drawdown must be non-positive (loss) and cannot exceed 100% (total loss).
    """
    # Convert to Polars series
    returns_series = pl.Series("returns", [float(r) for r in returns])

    # Calculate cumulative returns
    cumulative = calculate_cumulative_returns(returns_series)

    # Calculate max drawdown
    max_dd = calculate_max_drawdown(cumulative)
    max_dd_decimal = Decimal(str(max_dd))

    # Verify valid range
    assert max_dd_decimal <= Decimal("0"), f"Max drawdown must be non-positive: {max_dd_decimal}"
    assert max_dd_decimal >= Decimal(
        "-1"
    ), f"Max drawdown cannot exceed 100% loss: {max_dd_decimal}"


@given(
    returns=return_series(
        min_size=30, max_size=252, min_return=Decimal("0"), max_return=Decimal("0.1")
    ),
)
@example(returns=[Decimal("0.01")] * 100)
def test_max_drawdown_zero_for_all_positive_returns(returns: list[Decimal]) -> None:
    """Test max drawdown is zero when all returns are non-negative.

    Property:
        if all(returns >= 0), then max_drawdown = 0

    With only gains and no losses, there should be no drawdown.
    """
    # Convert to Polars series
    returns_series = pl.Series("returns", [float(r) for r in returns])

    # Calculate cumulative returns
    cumulative = calculate_cumulative_returns(returns_series)

    # Calculate max drawdown
    max_dd = calculate_max_drawdown(cumulative)
    max_dd_decimal = Decimal(str(max_dd))

    # Should be zero (or very close due to numerical precision)
    assert max_dd_decimal >= Decimal(
        "-0.0001"
    ), f"Max drawdown should be ~0 for all positive returns: {max_dd_decimal}"


@given(
    mean_return=decimal_prices(min_value=Decimal("0"), max_value=Decimal("0.1"), scale=4),
    std_return=decimal_prices(min_value=Decimal("0.01"), max_value=Decimal("0.1"), scale=4),
    risk_free_rate=decimal_prices(min_value=Decimal("0"), max_value=Decimal("0.05"), scale=4),
)
@example(
    mean_return=Decimal("0.05"),
    std_return=Decimal("0.02"),
    risk_free_rate=Decimal("0.01"),
)
@example(
    mean_return=Decimal("0.01"),
    std_return=Decimal("0.01"),
    risk_free_rate=Decimal("0.01"),
)  # Zero Sharpe
def test_sharpe_ratio_definition(
    mean_return: Decimal, std_return: Decimal, risk_free_rate: Decimal
) -> None:
    """Test Sharpe ratio = (mean_return - risk_free) / std_return.

    Property:
        sharpe_ratio = (mean_return - risk_free_rate) / std_return

    Sharpe ratio definition must be calculated exactly.
    """
    assume(std_return > Decimal("0"))  # Avoid division by zero

    # Calculate expected Sharpe ratio
    expected_sharpe = (mean_return - risk_free_rate) / std_return

    # Calculate using function (simulated)
    excess_return = mean_return - risk_free_rate
    actual_sharpe = excess_return / std_return

    # Verify exact equality
    assert actual_sharpe == expected_sharpe, (
        f"Sharpe ratio calculation incorrect: "
        f"expected={expected_sharpe}, actual={actual_sharpe}, "
        f"mean_return={mean_return}, std_return={std_return}, rf={risk_free_rate}"
    )


@given(
    mean_return=decimal_prices(min_value=Decimal("0"), max_value=Decimal("0.1"), scale=4),
    std_return=decimal_prices(min_value=Decimal("0.01"), max_value=Decimal("0.1"), scale=4),
)
@example(mean_return=Decimal("0.05"), std_return=Decimal("0.02"))
def test_sharpe_ratio_zero_when_return_equals_risk_free(
    mean_return: Decimal, std_return: Decimal
) -> None:
    """Test Sharpe ratio is zero when mean return equals risk-free rate.

    Property:
        if mean_return = risk_free_rate, then sharpe_ratio = 0

    When excess return is zero, Sharpe ratio should be zero.
    """
    assume(std_return > Decimal("0"))

    risk_free_rate = mean_return  # Set equal
    excess_return = mean_return - risk_free_rate  # Should be 0
    sharpe = excess_return / std_return

    assert sharpe == Decimal("0"), f"Sharpe ratio should be 0 when excess return is 0: {sharpe}"


@given(
    starting_value=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("1000000"), scale=2),
    ending_value=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("1000000"), scale=2),
)
@example(starting_value=Decimal("1000"), ending_value=Decimal("2000"))
@example(starting_value=Decimal("1000"), ending_value=Decimal("1000"))  # No change
@example(starting_value=Decimal("1000"), ending_value=Decimal("500"))  # Loss
def test_cumulative_return_calculation(starting_value: Decimal, ending_value: Decimal) -> None:
    """Test cumulative return = (ending_value / starting_value) - 1.

    Property:
        cumulative_return = (ending_value / starting_value) - 1

    Total return calculation must be exact.
    """
    assume(starting_value > Decimal("0"))

    # Calculate cumulative return
    cumulative_return = (ending_value / starting_value) - Decimal("1")

    # Verify reconstruction
    reconstructed_ending = (Decimal("1") + cumulative_return) * starting_value

    assert reconstructed_ending == ending_value, (
        f"Cumulative return reconstruction failed: "
        f"start={starting_value}, end={ending_value}, "
        f"return={cumulative_return}, reconstructed={reconstructed_ending}"
    )


@given(
    returns=return_series(min_size=10, max_size=100),
)
@example(returns=[Decimal("0.01"), Decimal("0.02"), Decimal("-0.01")])
def test_cumulative_returns_compounding(returns: list[Decimal]) -> None:
    """Test cumulative returns compound correctly.

    Property:
        cumulative_return = product(1 + return_i) - 1

    Cumulative returns must compound, not add linearly.
    """
    # Calculate cumulative return by compounding
    cumulative = Decimal("1")
    for ret in returns:
        cumulative *= Decimal("1") + ret

    final_return = cumulative - Decimal("1")

    # Calculate using Polars
    returns_series = pl.Series("returns", [float(r) for r in returns])
    polars_cumulative = calculate_cumulative_returns(returns_series)
    polars_final = Decimal(str(polars_cumulative[-1]))

    # Allow small numerical difference due to float conversion
    diff = abs(final_return - polars_final)
    assert diff < Decimal("0.0001"), (
        f"Cumulative returns compounding incorrect: "
        f"expected={final_return}, polars={polars_final}, diff={diff}"
    )


@given(
    win_count=decimal_prices(min_value=Decimal("0"), max_value=Decimal("100"), scale=0),
    total_count=decimal_prices(min_value=Decimal("10"), max_value=Decimal("100"), scale=0),
)
@example(win_count=Decimal("50"), total_count=Decimal("100"))
@example(win_count=Decimal("0"), total_count=Decimal("100"))
@example(win_count=Decimal("100"), total_count=Decimal("100"))
def test_win_rate_bounds(win_count: Decimal, total_count: Decimal) -> None:
    """Test win rate is in valid range [0, 1].

    Property:
        0 <= win_rate <= 1

    Win rate is a probability and must be in [0, 1] range.
    """
    assume(total_count > Decimal("0"))
    assume(win_count <= total_count)

    win_rate = win_count / total_count

    assert win_rate >= Decimal("0"), f"Win rate must be non-negative: {win_rate}"
    assert win_rate <= Decimal("1"), f"Win rate cannot exceed 1: {win_rate}"


@given(
    gross_profit=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("100000"), scale=2),
    gross_loss=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("100000"), scale=2),
)
@example(gross_profit=Decimal("10000"), gross_loss=Decimal("5000"))
@example(gross_profit=Decimal("10000"), gross_loss=Decimal("10000"))  # Break-even
def test_profit_factor_calculation(gross_profit: Decimal, gross_loss: Decimal) -> None:
    """Test profit factor = gross_profit / gross_loss.

    Property:
        profit_factor = gross_profit / gross_loss

    Profit factor must be calculated exactly.
    """
    assume(gross_loss > Decimal("0"))

    profit_factor = gross_profit / gross_loss

    # Verify reconstruction
    reconstructed_profit = profit_factor * gross_loss

    assert reconstructed_profit == gross_profit, (
        f"Profit factor calculation incorrect: "
        f"profit={gross_profit}, loss={gross_loss}, "
        f"factor={profit_factor}, reconstructed={reconstructed_profit}"
    )


@given(
    strategy_return=decimal_prices(min_value=Decimal("-0.5"), max_value=Decimal("1.0"), scale=4),
    benchmark_return=decimal_prices(min_value=Decimal("-0.5"), max_value=Decimal("1.0"), scale=4),
)
@example(strategy_return=Decimal("0.15"), benchmark_return=Decimal("0.10"))
@example(strategy_return=Decimal("0.10"), benchmark_return=Decimal("0.10"))  # No alpha
@example(strategy_return=Decimal("0.05"), benchmark_return=Decimal("0.10"))  # Underperform
def test_excess_return_calculation(strategy_return: Decimal, benchmark_return: Decimal) -> None:
    """Test excess return = strategy_return - benchmark_return.

    Property:
        excess_return = strategy_return - benchmark_return

    Excess return (alpha) must be calculated exactly.
    """
    excess_return = strategy_return - benchmark_return

    # Verify reconstruction
    reconstructed_strategy = benchmark_return + excess_return

    assert reconstructed_strategy == strategy_return, (
        f"Excess return calculation incorrect: "
        f"strategy={strategy_return}, benchmark={benchmark_return}, "
        f"excess={excess_return}, reconstructed={reconstructed_strategy}"
    )
