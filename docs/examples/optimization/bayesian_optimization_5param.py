"""Bayesian Optimization Example with 5-Parameter Strategy.

This example demonstrates Bayesian optimization on a momentum strategy
with 5 parameters, comparing it to Grid Search and Random Search.

Bayesian optimization is more sample-efficient than grid/random search,
finding good parameters with fewer evaluations.
"""

from decimal import Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.optimization.search import (
    BayesianOptimizer,
    RandomSearchAlgorithm,
)

# Create output directory for plots
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)


def momentum_strategy_objective(params: dict) -> Decimal:
    """Simulate a momentum strategy objective function.

    This is a synthetic objective that mimics backtesting a momentum strategy
    with the given parameters. In a real scenario, this would run an actual backtest.

    Parameters:
        lookback_short: Short lookback period
        lookback_long: Long lookback period
        threshold: Signal threshold
        rebalance_freq: Rebalancing frequency (days)
        ma_type: Moving average type

    Returns:
        Sharpe ratio (higher is better)
    """
    short = float(params["lookback_short"])
    long = float(params["lookback_long"])
    threshold = float(params["threshold"])
    rebalance = float(params["rebalance_freq"])
    ma_type = params["ma_type"]

    # Synthetic objective with known optimal region:
    # - lookback_short: 20
    # - lookback_long: 100
    # - threshold: 0.02
    # - rebalance_freq: 5
    # - ma_type: ema

    # Distance from optimal
    score = -(
        abs(short - 20) / 20
        + abs(long - 100) / 100
        + abs(threshold - 0.02) / 0.02
        + abs(rebalance - 5) / 5
    )

    # Bonus for EMA
    if ma_type == "ema":
        score += 0.5

    # Add some noise to simulate backtest variance
    noise = np.random.normal(0, 0.1)
    score += noise

    # Convert to Sharpe-like metric (0-3 range)
    sharpe = max(0, min(3, 1.5 + score))

    return Decimal(str(sharpe))


def main():
    """Run Bayesian optimization example."""
    print("=" * 80)
    print("Bayesian Optimization Example - 5 Parameter Momentum Strategy")
    print("=" * 80)

    # Define parameter space
    param_space = ParameterSpace(
        parameters=[
            ContinuousParameter(name="lookback_short", min_value=10.0, max_value=50.0),
            ContinuousParameter(name="lookback_long", min_value=50.0, max_value=200.0),
            ContinuousParameter(
                name="threshold",
                min_value=0.01,
                max_value=0.1,
                prior="log-uniform",  # Log-uniform for wide range
            ),
            DiscreteParameter(name="rebalance_freq", min_value=1, max_value=10, step=1),
            CategoricalParameter(name="ma_type", choices=["ema", "sma", "wma"]),
        ]
    )

    print(f"\nParameter Space ({len(param_space.parameters)} parameters):")
    for p in param_space.parameters:
        print(f"  - {p.name}: {p}")

    # ==================== Bayesian Optimization ====================
    print("\n" + "=" * 80)
    print("1. Bayesian Optimization (Expected Improvement)")
    print("=" * 80)

    bayes_optimizer = BayesianOptimizer(
        parameter_space=param_space,
        n_iter=50,
        acq_func="EI",
        kappa=1.96,
        xi=0.01,
        random_state=42,
    )

    print("\nRunning 50 iterations...")
    bayes_evaluations = []

    while not bayes_optimizer.is_complete():
        params = bayes_optimizer.suggest()
        score = momentum_strategy_objective(params)
        bayes_optimizer.update(params, score)
        bayes_evaluations.append(float(score))

        if bayes_optimizer.iteration % 10 == 0:
            best = bayes_optimizer.get_best_score()
            print(f"  Iteration {bayes_optimizer.iteration}: Best Sharpe = {best}")

    best_params = bayes_optimizer.get_best_params()
    best_score = bayes_optimizer.get_best_score()

    print("\nBayesian Optimization Results:")
    print(f"  Best Sharpe Ratio: {best_score}")
    print("  Best Parameters:")
    for key, value in best_params.items():
        print(f"    {key}: {value}")
    print(f"  Total Evaluations: {bayes_optimizer.iteration}")

    # ==================== Bayesian with Prior Knowledge ====================
    print("\n" + "=" * 80)
    print("2. Bayesian Optimization with Prior Knowledge")
    print("=" * 80)

    # Seed with a known reasonable parameter set
    initial_points = [
        {
            "lookback_short": 15.0,
            "lookback_long": 90.0,
            "threshold": 0.025,
            "rebalance_freq": 4,
            "ma_type": "ema",
        }
    ]
    initial_scores = [momentum_strategy_objective(initial_points[0])]

    bayes_prior_optimizer = BayesianOptimizer(
        parameter_space=param_space,
        n_iter=50,
        acq_func="EI",
        initial_points=initial_points,
        initial_scores=initial_scores,
        random_state=42,
    )

    print("\nSeeded with prior knowledge:")
    print(f"  Initial Sharpe: {initial_scores[0]}")

    print("\nRunning 50 iterations...")
    bayes_prior_evaluations = []

    while not bayes_prior_optimizer.is_complete():
        params = bayes_prior_optimizer.suggest()
        score = momentum_strategy_objective(params)
        bayes_prior_optimizer.update(params, score)
        bayes_prior_evaluations.append(float(score))

    best_prior_score = bayes_prior_optimizer.get_best_score()
    print("\nBayesian with Prior Results:")
    print(f"  Best Sharpe Ratio: {best_prior_score}")
    print(f"  Total Evaluations: {bayes_prior_optimizer.iteration}")

    # ==================== Random Search Comparison ====================
    print("\n" + "=" * 80)
    print("3. Random Search (for comparison)")
    print("=" * 80)

    random_optimizer = RandomSearchAlgorithm(parameter_space=param_space, n_iter=50)

    print("\nRunning 50 iterations...")
    random_evaluations = []

    while not random_optimizer.is_complete():
        params = random_optimizer.suggest()
        score = momentum_strategy_objective(params)
        random_optimizer.update(params, score)
        random_evaluations.append(float(score))

        if random_optimizer.iteration % 10 == 0:
            best = max(random_evaluations)
            print(f"  Iteration {random_optimizer.iteration}: Best Sharpe = {best:.4f}")

    random_best_score = Decimal(str(max(random_evaluations)))
    print("\nRandom Search Results:")
    print(f"  Best Sharpe Ratio: {random_best_score}")
    print(f"  Total Evaluations: {random_optimizer.iteration}")

    # ==================== Comparison Plot ====================
    print("\n" + "=" * 80)
    print("4. Comparison Visualization")
    print("=" * 80)

    # Compute cumulative best for each method
    bayes_cum_best = np.maximum.accumulate(bayes_evaluations)
    bayes_prior_cum_best = np.maximum.accumulate(bayes_prior_evaluations)
    random_cum_best = np.maximum.accumulate(random_evaluations)

    plt.figure(figsize=(12, 8))

    # Plot 1: Convergence comparison
    plt.subplot(2, 2, 1)
    plt.plot(bayes_cum_best, label="Bayesian (EI)", linewidth=2)
    plt.plot(bayes_prior_cum_best, label="Bayesian + Prior", linewidth=2, linestyle="--")
    plt.plot(random_cum_best, label="Random Search", linewidth=2, linestyle=":")
    plt.xlabel("Iteration")
    plt.ylabel("Best Sharpe Ratio")
    plt.title("Convergence Comparison")
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Plot 2: All evaluations
    plt.subplot(2, 2, 2)
    plt.scatter(range(len(bayes_evaluations)), bayes_evaluations, alpha=0.5, s=30)
    plt.plot(bayes_cum_best, "r-", linewidth=2, label="Best")
    plt.xlabel("Iteration")
    plt.ylabel("Sharpe Ratio")
    plt.title("Bayesian Optimization Evaluations")
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Plot 3: Improvement per iteration
    plt.subplot(2, 2, 3)
    bayes_improvements = np.diff(bayes_cum_best, prepend=bayes_cum_best[0])
    random_improvements = np.diff(random_cum_best, prepend=random_cum_best[0])
    plt.bar(
        range(len(bayes_improvements)),
        bayes_improvements,
        alpha=0.6,
        label="Bayesian",
    )
    plt.bar(
        range(len(random_improvements)),
        random_improvements,
        alpha=0.6,
        label="Random",
    )
    plt.xlabel("Iteration")
    plt.ylabel("Improvement")
    plt.title("Improvement Per Iteration")
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Plot 4: Final comparison
    plt.subplot(2, 2, 4)
    methods = ["Bayesian\n(EI)", "Bayesian\n+ Prior", "Random\nSearch"]
    scores = [float(best_score), float(best_prior_score), float(random_best_score)]
    colors = ["#2ecc71", "#3498db", "#e74c3c"]
    bars = plt.bar(methods, scores, color=colors, alpha=0.7)
    plt.ylabel("Best Sharpe Ratio")
    plt.title("Final Best Scores (50 iterations each)")
    plt.ylim(0, max(scores) * 1.2)
    for bar, score in zip(bars, scores, strict=False):
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{score:.3f}",
            ha="center",
            va="bottom",
        )

    plt.tight_layout()
    comparison_path = OUTPUT_DIR / "bayesian_comparison.png"
    plt.savefig(comparison_path, dpi=300, bbox_inches="tight")
    print(f"\nSaved comparison plot to: {comparison_path}")

    # ==================== Bayesian-Specific Plots ====================
    print("\n" + "=" * 80)
    print("5. Bayesian Optimization Analysis Plots")
    print("=" * 80)

    # Convergence plot
    convergence_path = OUTPUT_DIR / "bayesian_convergence.png"
    bayes_optimizer.plot_convergence(save_path=convergence_path)
    print(f"  Saved convergence plot to: {convergence_path}")

    # Objective plot (parameter importance)
    objective_path = OUTPUT_DIR / "bayesian_objective.png"
    bayes_optimizer.plot_objective(save_path=objective_path)
    print(f"  Saved objective plot to: {objective_path}")

    # Evaluations plot
    evaluations_path = OUTPUT_DIR / "bayesian_evaluations.png"
    bayes_optimizer.plot_evaluations(save_path=evaluations_path)
    print(f"  Saved evaluations plot to: {evaluations_path}")

    plt.close("all")

    # ==================== Summary ====================
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print("\nBest Scores (50 evaluations each):")
    print(f"  1. Bayesian (EI):     {best_score:.4f}")
    print(f"  2. Bayesian + Prior:  {best_prior_score:.4f}")
    print(f"  3. Random Search:     {random_best_score:.4f}")

    improvement = (float(best_score) - float(random_best_score)) / float(random_best_score) * 100
    print(f"\nBayesian improvement over Random: {improvement:+.1f}%")

    print("\nKey Takeaways:")
    print("  - Bayesian optimization finds better solutions with fewer evaluations")
    print("  - Prior knowledge can significantly accelerate convergence")
    print("  - Acquisition functions balance exploration and exploitation")
    print("  - Most effective for expensive objectives (minutes per evaluation)")
    print("  - Works best with 2-20 continuous parameters")

    print("\n" + "=" * 80)
    print("Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    # Set random seed for reproducibility
    np.random.seed(42)
    main()
