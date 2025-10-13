"""Performance comparison: Random Search vs Grid Search.

This example demonstrates how Random Search can find good parameters faster
than Grid Search in high-dimensional spaces, based on the research by
Bergstra & Bengio (2012).
"""

import time
from decimal import Decimal

from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.optimization.search import GridSearchAlgorithm, RandomSearchAlgorithm


def mock_strategy_backtest(params: dict) -> dict:
    """Simulate running a backtest with given parameters.

    In reality this would run a full backtest. For demonstration, we'll
    compute a mock Sharpe ratio based on parameters.
    """
    # Mock objective function - penalize extreme values
    ma_short = params["ma_short"]
    ma_long = params["ma_long"]
    threshold = float(params["threshold"])

    # Optimal around ma_short=20, ma_long=50, threshold=0.02
    sharpe = Decimal("2.5")
    sharpe -= abs(ma_short - 20) * Decimal("0.01")
    sharpe -= abs(ma_long - 50) * Decimal("0.01")
    sharpe -= abs(Decimal(str(threshold)) - Decimal("0.02")) * Decimal("50")

    # Simulate backtest time
    time.sleep(0.01)

    return {"sharpe_ratio": sharpe}


def run_grid_search_demo():
    """Demonstrate Grid Search on 3-parameter space."""
    print("\n" + "=" * 60)
    print("GRID SEARCH - Exhaustive Search")
    print("=" * 60)

    # Define parameter space for Grid Search (discrete only)
    param_space = ParameterSpace(
        parameters=[
            DiscreteParameter(name="ma_short", min_value=10, max_value=30, step=5),
            DiscreteParameter(name="ma_long", min_value=40, max_value=60, step=5),
            CategoricalParameter(name="threshold", choices=[0.01, 0.02, 0.03]),
        ]
    )

    print(f"\nParameter space cardinality: {param_space.cardinality()}")
    print("Parameters:")
    print("  - ma_short: [10, 15, 20, 25, 30] (5 values)")
    print("  - ma_long: [40, 45, 50, 55, 60] (5 values)")
    print("  - threshold: [0.01, 0.02, 0.03] (3 values)")
    print(f"  Total combinations: 5 × 5 × 3 = {param_space.cardinality()}")

    grid_search = GridSearchAlgorithm(parameter_space=param_space)

    start_time = time.time()
    trial_count = 0
    best_sharpe = Decimal("-Infinity")

    while not grid_search.is_complete():
        params = grid_search.suggest()
        result = mock_strategy_backtest(params)
        sharpe = result["sharpe_ratio"]
        grid_search.update(params, sharpe)

        trial_count += 1
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            print(f"\nTrial {trial_count}: New best Sharpe = {sharpe:.4f}")
            print(f"  Parameters: {params}")

    elapsed = time.time() - start_time

    best_params = grid_search.get_best_params()
    best_result, best_score = grid_search.get_results()[0]

    print(f"\n{'─' * 60}")
    print("GRID SEARCH RESULTS:")
    print(f"  Trials completed: {trial_count}")
    print(f"  Time elapsed: {elapsed:.2f}s")
    print(f"  Best Sharpe: {best_score:.4f}")
    print(f"  Best params: {best_params}")

    return trial_count, elapsed, best_score


def run_random_search_demo():
    """Demonstrate Random Search on 3-parameter space."""
    print("\n" + "=" * 60)
    print("RANDOM SEARCH - Probabilistic Sampling")
    print("=" * 60)

    # Same space but continuous parameters (infinite combinations)
    param_space = ParameterSpace(
        parameters=[
            ContinuousParameter(
                name="ma_short",
                min_value=Decimal("10"),
                max_value=Decimal("30"),
                prior="uniform",
            ),
            ContinuousParameter(
                name="ma_long",
                min_value=Decimal("40"),
                max_value=Decimal("60"),
                prior="uniform",
            ),
            ContinuousParameter(
                name="threshold",
                min_value=Decimal("0.01"),
                max_value=Decimal("0.03"),
                prior="uniform",
            ),
        ]
    )

    # Sample 50 random combinations (much less than 75 grid points)
    n_iter = 50
    print("\nParameter space: Continuous (infinite combinations)")
    print("  - ma_short: [10, 30] (continuous)")
    print("  - ma_long: [40, 60] (continuous)")
    print("  - threshold: [0.01, 0.03] (continuous)")
    print(f"\nRandom samples: {n_iter}")

    random_search = RandomSearchAlgorithm(parameter_space=param_space, n_iter=n_iter, seed=42)

    start_time = time.time()
    trial_count = 0
    best_sharpe = Decimal("-Infinity")

    while not random_search.is_complete():
        params = random_search.suggest()
        # Convert Decimals to integers for ma parameters
        params_eval = params.copy()
        params_eval["ma_short"] = int(params["ma_short"])
        params_eval["ma_long"] = int(params["ma_long"])

        result = mock_strategy_backtest(params_eval)
        sharpe = result["sharpe_ratio"]
        random_search.update(params, sharpe)

        trial_count += 1
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            print(f"\nTrial {trial_count}: New best Sharpe = {sharpe:.4f}")
            print(
                f"  Parameters: ma_short={params['ma_short']:.1f}, "
                f"ma_long={params['ma_long']:.1f}, "
                f"threshold={params['threshold']:.4f}"
            )

    elapsed = time.time() - start_time

    best_params = random_search.get_best_params()
    best_score = random_search.get_best_result()[1]

    print(f"\n{'─' * 60}")
    print("RANDOM SEARCH RESULTS:")
    print(f"  Trials completed: {trial_count}")
    print(f"  Time elapsed: {elapsed:.2f}s")
    print(f"  Best Sharpe: {best_score:.4f}")
    print(
        f"  Best params: ma_short={best_params['ma_short']:.2f}, "
        f"ma_long={best_params['ma_long']:.2f}, "
        f"threshold={best_params['threshold']:.4f}"
    )

    return trial_count, elapsed, best_score


def main():
    """Compare Grid Search vs Random Search performance."""
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  Performance Comparison: Grid Search vs Random Search".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "═" * 58 + "╝")

    # Run Grid Search
    grid_trials, grid_time, grid_best = run_grid_search_demo()

    # Run Random Search
    random_trials, random_time, random_best = run_random_search_demo()

    # Comparison
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    speedup = grid_time / random_time if random_time > 0 else 0
    efficiency = (grid_trials / random_trials) if random_trials > 0 else 0

    print("\nTrials:")
    print(f"  Grid Search:   {grid_trials:3d} trials")
    print(f"  Random Search: {random_trials:3d} trials")
    print(f"  Efficiency:    {efficiency:.2f}× fewer trials")

    print("\nTime:")
    print(f"  Grid Search:   {grid_time:.2f}s")
    print(f"  Random Search: {random_time:.2f}s")
    print(f"  Speedup:       {speedup:.2f}× faster")

    print("\nBest Result:")
    print(f"  Grid Search:   Sharpe = {grid_best:.4f}")
    print(f"  Random Search: Sharpe = {random_best:.4f}")
    quality_ratio = float(random_best) / float(grid_best) if grid_best > 0 else 0
    print(f"  Quality:       {quality_ratio:.1%} of optimal")

    print("\n" + "─" * 60)
    print("KEY TAKEAWAY:")
    print("─" * 60)
    print("Random Search achieves comparable results with ~33% fewer")
    print("evaluations. This advantage grows exponentially with more")
    print("parameters (curse of dimensionality).")
    print("\nFor 5+ parameters, Random Search is typically 5-10× faster")
    print("while finding solutions within 95% of optimal.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
