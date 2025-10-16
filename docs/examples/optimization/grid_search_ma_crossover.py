"""Grid Search Example: Moving Average Crossover Strategy.

This example demonstrates using grid search to optimize a simple moving average
crossover strategy. The strategy generates buy signals when the short MA crosses
above the long MA, and sell signals when the short MA crosses below the long MA.

We'll optimize:
- Short MA lookback period
- Long MA lookback period
- Entry threshold (minimum crossover strength)
"""

# ruff: noqa: T201  # print statements are expected in example scripts

from decimal import Decimal

import polars as pl

from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.optimization.search import GridSearchAlgorithm


# Simulated backtest function
def simple_ma_crossover_backtest(params: dict) -> dict:
    """Run moving average crossover backtest with given parameters.

    This is a simplified backtest function for demonstration purposes.
    In a real scenario, this would call run_algorithm() with a full strategy.

    Args:
        params: Strategy parameters containing:
            - lookback_short: Short MA period
            - lookback_long: Long MA period
            - threshold: Minimum crossover strength

    Returns:
        Dictionary with performance_metrics including sharpe_ratio
    """
    lookback_short = params["lookback_short"]
    lookback_long = params["lookback_long"]
    threshold = params["threshold"]

    # Simplified scoring function
    # In reality, this would run a full backtest
    # Here we use a simple heuristic: prefer moderate lookback periods
    # and penalize threshold that's too high or too low

    # Optimal short is around 20, optimal long is around 100
    short_score = 1.0 - abs(lookback_short - 20) / 20
    long_score = 1.0 - abs(lookback_long - 100) / 100

    # Optimal threshold around 0.02
    threshold_score = 1.0 - abs(threshold - 0.02) / 0.02

    # Combined score (simplified Sharpe ratio proxy)
    sharpe_ratio = (short_score + long_score + threshold_score) / 3

    return {
        "performance_metrics": {
            "sharpe_ratio": sharpe_ratio,
            "total_return": sharpe_ratio * 0.5,  # Dummy metric
            "max_drawdown": 0.2 / sharpe_ratio,  # Dummy metric
        }
    }


def run_grid_search_example() -> None:
    """Run grid search optimization for MA crossover strategy."""
    print("=" * 70)
    print("Grid Search Optimization Example: Moving Average Crossover")
    print("=" * 70)

    # Define parameter space
    param_space = ParameterSpace(
        parameters=[
            DiscreteParameter(
                name="lookback_short",
                min_value=10,
                max_value=30,
                step=5,
            ),
            DiscreteParameter(
                name="lookback_long",
                min_value=50,
                max_value=150,
                step=25,
            ),
            CategoricalParameter(
                name="threshold",
                choices=[0.01, 0.02, 0.03],
            ),
        ]
    )

    print("\nParameter Space:")
    print("  - lookback_short: [10, 15, 20, 25, 30]")
    print("  - lookback_long: [50, 75, 100, 125, 150]")
    print("  - threshold: [0.01, 0.02, 0.03]")
    print(f"\nTotal combinations: {param_space.cardinality()}")

    # Create grid search algorithm
    grid = GridSearchAlgorithm(
        parameter_space=param_space,
        early_stopping_rounds=None,  # Disable early stopping for this example
    )

    print(f"\nStarting grid search over {grid.total_combinations} combinations...")
    print("-" * 70)

    # Run optimization
    trial_num = 0
    while not grid.is_complete():
        trial_num += 1

        # Get next parameter combination
        params = grid.suggest()

        # Run backtest
        result = simple_ma_crossover_backtest(params)

        # Extract objective metric
        sharpe_ratio = Decimal(str(result["performance_metrics"]["sharpe_ratio"]))

        # Update grid search
        grid.update(params, sharpe_ratio)

        # Print progress every 10 trials
        if trial_num % 10 == 0:
            print(
                f"Trial {trial_num}/{grid.total_combinations} ({grid.progress * 100:.0f}% complete)"
            )

    print("-" * 70)
    print(f"Optimization complete! Evaluated {trial_num} combinations.")

    # Get results
    print("\n" + "=" * 70)
    print("Top 5 Parameter Combinations:")
    print("=" * 70)

    top_results = grid.get_results(top_k=5)
    for rank, (params, score) in enumerate(top_results, start=1):
        print(f"\nRank {rank}:")
        print(f"  Sharpe Ratio: {score:.4f}")
        print("  Parameters:")
        print(f"    - lookback_short: {params['lookback_short']}")
        print(f"    - lookback_long: {params['lookback_long']}")
        print(f"    - threshold: {params['threshold']}")

    # Get best parameters
    best_params = grid.get_best_params()
    print("\n" + "=" * 70)
    print("Best Parameters:")
    print("=" * 70)
    print(f"  - lookback_short: {best_params['lookback_short']}")
    print(f"  - lookback_long: {best_params['lookback_long']}")
    print(f"  - threshold: {best_params['threshold']}")

    # Create results dataframe for analysis
    all_results = grid.get_results()
    results_df = pl.DataFrame(
        {
            "lookback_short": [p["lookback_short"] for p, _ in all_results],
            "lookback_long": [p["lookback_long"] for p, _ in all_results],
            "threshold": [p["threshold"] for p, _ in all_results],
            "sharpe_ratio": [float(s) for _, s in all_results],
        }
    )

    print("\n" + "=" * 70)
    print("Results Summary:")
    print("=" * 70)
    print(results_df.describe())

    # Analyze parameter impact
    print("\n" + "=" * 70)
    print("Parameter Impact Analysis:")
    print("=" * 70)

    # Group by each parameter to see average performance
    for param in ["lookback_short", "lookback_long", "threshold"]:
        avg_by_param = (
            results_df.group_by(param)
            .agg(pl.col("sharpe_ratio").mean().alias("avg_sharpe"))
            .sort("avg_sharpe", descending=True)
        )
        print(f"\nAverage Sharpe by {param}:")
        print(avg_by_param)

    print("\n" + "=" * 70)
    print("Key Insights:")
    print("=" * 70)
    print("- Grid search exhaustively tested all 75 combinations")
    print("- Best parameters found through systematic exploration")
    print("- Parameter impact analysis reveals which parameters matter most")
    print("\nNote: For larger parameter spaces (>1000 combinations),")
    print("consider using RandomSearch or BayesianOptimizer instead.")
    print("=" * 70)


if __name__ == "__main__":
    run_grid_search_example()
