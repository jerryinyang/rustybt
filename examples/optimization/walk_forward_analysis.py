"""Walk-Forward Optimization Example.

Demonstrates walk-forward optimization to validate strategy robustness
across multiple time windows and detect overfitting.
"""

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from rustybt.optimization import (
    DiscreteParameter,
    ObjectiveFunction,
    ParameterSpace,
)
from rustybt.optimization.search import RandomSearchAlgorithm
from rustybt.optimization.walk_forward import WalkForwardOptimizer, WindowConfig

# Set plot style
plt.style.use("seaborn-v0_8-darkgrid")


def create_synthetic_price_data(n_days: int = 730, seed: int = 42) -> pl.DataFrame:
    """Create synthetic price data with regime changes.

    Args:
        n_days: Number of days of data to generate
        seed: Random seed for reproducibility

    Returns:
        DataFrame with date and price columns
    """
    np.random.seed(seed)

    # Create dates (2 years)
    from datetime import datetime, timedelta

    start_date = datetime(2021, 1, 1)
    end_date = start_date + timedelta(days=n_days - 1)

    dates = pl.date_range(start=start_date, end=end_date, interval="1d", eager=True)

    # Generate returns with regime changes
    # First 250 days: low volatility, positive drift
    returns_1 = np.random.randn(250) * 0.01 + 0.0005

    # Next 250 days: high volatility, no drift (harder to trade)
    returns_2 = np.random.randn(250) * 0.025

    # Last 230 days: moderate volatility, positive drift
    returns_3 = np.random.randn(n_days - 500) * 0.015 + 0.0003

    returns = np.concatenate([returns_1, returns_2, returns_3])

    # Generate prices from returns
    prices = 100.0 * (1 + returns).cumprod()

    # Add some trend-following signal (moving average would work here)
    return pl.DataFrame({"date": dates, "price": prices, "returns": returns})


def simple_ma_strategy_backtest(params: dict, data: pl.DataFrame) -> dict:
    """Simple moving average crossover strategy backtest.

    Args:
        params: Dictionary with 'fast_ma' and 'slow_ma' parameters
        data: Price data DataFrame

    Returns:
        Dictionary with performance metrics
    """
    fast_ma = int(params["fast_ma"])
    slow_ma = int(params["slow_ma"])

    # Calculate moving averages
    prices = data["price"].to_numpy()

    if len(prices) < slow_ma + 1:
        # Not enough data
        return {
            "performance_metrics": {
                "sharpe_ratio": 0.0,
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
            }
        }

    # Calculate moving averages manually to control alignment
    fast_ma_values = []
    slow_ma_values = []

    for i in range(slow_ma, len(prices)):
        # Calculate both MAs for same price point
        fast_avg = prices[i - fast_ma : i].mean()
        slow_avg = prices[i - slow_ma : i].mean()
        fast_ma_values.append(fast_avg)
        slow_ma_values.append(slow_avg)

    fast_ma_values = np.array(fast_ma_values)
    slow_ma_values = np.array(slow_ma_values)

    # Generate signals
    signals = np.where(fast_ma_values > slow_ma_values, 1, -1)

    # Calculate returns - align with signals
    # Returns start at slow_ma index (after we have enough data for slow MA)
    returns = data["returns"].to_numpy()
    aligned_returns = returns[slow_ma : slow_ma + len(signals)]
    strategy_returns = signals * aligned_returns

    if len(strategy_returns) == 0:
        return {
            "performance_metrics": {
                "sharpe_ratio": 0.0,
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
            }
        }

    # Calculate metrics
    mean_return = strategy_returns.mean()
    std_return = strategy_returns.std()

    sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0.0  # Annualized
    total_return = (1 + strategy_returns).prod() - 1

    # Calculate max drawdown
    cumulative = (1 + strategy_returns).cumprod()
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0

    # Win rate
    win_rate = (strategy_returns > 0).sum() / len(strategy_returns)

    return {
        "performance_metrics": {
            "sharpe_ratio": float(sharpe),
            "total_return": float(total_return),
            "max_drawdown": float(max_drawdown),
            "win_rate": float(win_rate),
        }
    }


def main():
    """Run walk-forward optimization example."""
    print("=" * 80)
    print("WALK-FORWARD OPTIMIZATION EXAMPLE")
    print("=" * 80)
    print()

    # Create synthetic data
    print("1. Creating synthetic price data (2 years, with regime changes)...")
    data = create_synthetic_price_data(n_days=730, seed=42)
    print(f"   Data shape: {data.shape}")
    print(f"   Date range: {data['date'][0]} to {data['date'][-1]}")
    print()

    # Define parameter space
    print("2. Defining parameter space...")
    param_space = ParameterSpace(
        parameters=[
            DiscreteParameter(name="fast_ma", min_value=5, max_value=20, step=5),
            DiscreteParameter(name="slow_ma", min_value=30, max_value=60, step=10),
        ]
    )
    print(f"   Parameters: {[p.name for p in param_space.parameters]}")
    print()

    # Configure walk-forward windows
    print("3. Configuring walk-forward windows...")
    config = WindowConfig(
        train_period=150,  # 150 days for training
        validation_period=50,  # 50 days for validation
        test_period=50,  # 50 days for out-of-sample testing
        step_size=50,  # Advance 50 days each window
        window_type="rolling",  # Fixed window size
    )
    print(f"   Train period: {config.train_period} days")
    print(f"   Validation period: {config.validation_period} days")
    print(f"   Test period: {config.test_period} days")
    print(f"   Step size: {config.step_size} days")
    print(f"   Window type: {config.window_type}")
    print()

    # Create walk-forward optimizer
    print("4. Creating walk-forward optimizer...")
    optimizer = WalkForwardOptimizer(
        parameter_space=param_space,
        search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=20, seed=42),
        objective_function=ObjectiveFunction(metric="sharpe_ratio"),
        backtest_function=simple_ma_strategy_backtest,
        config=config,
        max_trials_per_window=20,
    )
    print("   Search algorithm: RandomSearchAlgorithm")
    print("   Objective: Sharpe ratio")
    print("   Max trials per window: 20")
    print()

    # Run walk-forward optimization
    print("5. Running walk-forward optimization...")
    print("   (This may take a minute...)")
    print()
    result = optimizer.run(data)

    # Display results
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    print(f"Number of windows: {result.num_windows}")
    print()

    # Aggregate metrics
    print("Aggregate Performance (across all windows):")
    print("-" * 80)
    for phase in ["train", "validation", "test"]:
        print(f"\n{phase.upper()}:")
        phase_metrics = result.aggregate_metrics.get(phase, {})
        for metric_name in [
            "sharpe_ratio_mean",
            "sharpe_ratio_std",
            "total_return_mean",
            "max_drawdown_mean",
        ]:
            if metric_name in phase_metrics:
                value = phase_metrics[metric_name]
                print(f"  {metric_name}: {float(value):.4f}")

    # Parameter stability
    print()
    print("Parameter Stability:")
    print("-" * 80)
    for param_name, stability_stats in result.parameter_stability.items():
        print(f"\n{param_name}:")
        print(f"  Mean: {float(stability_stats['mean']):.2f}")
        print(f"  Std: {float(stability_stats['std']):.2f}")
        print(
            f"  Range: [{float(stability_stats['min']):.2f}, {float(stability_stats['max']):.2f}]"
        )
        print(
            f"  Coefficient of Variation: {float(stability_stats['coefficient_of_variation']):.2%}"
        )
        print(f"  Stable: {'✓ Yes' if stability_stats['is_stable'] else '✗ No (high drift)'}")

    # Individual window results
    print()
    print("Individual Window Results:")
    print("-" * 80)
    for window_result in result.window_results:
        print(f"\nWindow {window_result.window_id}:")
        print(f"  Best params: {window_result.best_params}")
        print(f"  Train Sharpe: {float(window_result.train_metrics.get('score', 0)):.3f}")
        print(f"  Validation Sharpe: {float(window_result.validation_metrics.get('score', 0)):.3f}")
        print(f"  Test Sharpe: {float(window_result.test_metrics.get('score', 0)):.3f}")

        # Check for overfitting
        val_score = float(window_result.validation_metrics.get("score", 0))
        test_score = float(window_result.test_metrics.get("score", 0))
        if val_score > 0 and test_score < val_score * 0.7:
            print("  ⚠️  Warning: Potential overfitting detected (test << validation)")

    # Visualizations
    print()
    print("6. Creating visualizations...")

    # Plot 1: Performance across windows
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Sharpe ratios
    ax1 = axes[0, 0]
    window_ids = [wr.window_id for wr in result.window_results]
    train_sharpes = [float(wr.train_metrics.get("score", 0)) for wr in result.window_results]
    val_sharpes = [float(wr.validation_metrics.get("score", 0)) for wr in result.window_results]
    test_sharpes = [float(wr.test_metrics.get("score", 0)) for wr in result.window_results]

    ax1.plot(window_ids, train_sharpes, "b-o", label="Train", linewidth=2)
    ax1.plot(window_ids, val_sharpes, "g-o", label="Validation", linewidth=2)
    ax1.plot(window_ids, test_sharpes, "r-o", label="Test (OOS)", linewidth=2)
    ax1.set_xlabel("Window ID")
    ax1.set_ylabel("Sharpe Ratio")
    ax1.set_title("Performance Across Windows")
    ax1.legend()
    ax1.grid(True)

    # Parameter evolution
    ax2 = axes[0, 1]
    fast_ma_values = [wr.best_params["fast_ma"] for wr in result.window_results]
    slow_ma_values = [wr.best_params["slow_ma"] for wr in result.window_results]

    ax2.plot(window_ids, fast_ma_values, "b-o", label="Fast MA", linewidth=2)
    ax2.plot(window_ids, slow_ma_values, "r-o", label="Slow MA", linewidth=2)
    ax2.set_xlabel("Window ID")
    ax2.set_ylabel("Parameter Value")
    ax2.set_title("Parameter Evolution Across Windows")
    ax2.legend()
    ax2.grid(True)

    # Overfitting detection (val vs test performance)
    ax3 = axes[1, 0]
    ax3.scatter(val_sharpes, test_sharpes, s=100, alpha=0.6)
    # Add diagonal line (perfect match)
    min_val = min(min(val_sharpes), min(test_sharpes))
    max_val = max(max(val_sharpes), max(test_sharpes))
    ax3.plot([min_val, max_val], [min_val, max_val], "k--", alpha=0.5, label="Perfect match")
    ax3.set_xlabel("Validation Sharpe")
    ax3.set_ylabel("Test Sharpe (OOS)")
    ax3.set_title("Overfitting Detection: Validation vs Test")
    ax3.legend()
    ax3.grid(True)

    # Distribution of test performance
    ax4 = axes[1, 1]
    ax4.hist(test_sharpes, bins=10, alpha=0.7, edgecolor="black")
    ax4.axvline(np.mean(test_sharpes), color="r", linestyle="--", linewidth=2, label="Mean")
    ax4.set_xlabel("Test Sharpe Ratio")
    ax4.set_ylabel("Frequency")
    ax4.set_title("Distribution of Out-of-Sample Performance")
    ax4.legend()
    ax4.grid(True)

    plt.tight_layout()
    plt.savefig("examples/optimization/output/walk_forward_results.png", dpi=150)
    print("   Saved: examples/optimization/output/walk_forward_results.png")

    # Summary
    print()
    print("=" * 80)
    print("KEY TAKEAWAYS")
    print("=" * 80)
    print()
    print("1. Walk-forward optimization validates strategy robustness across time")
    print("2. Test performance shows out-of-sample (OOS) reality (not inflated by overfitting)")
    print("3. Parameter stability indicates robust vs overfitted strategies:")
    print("   - Stable params (low CV) → Likely robust")
    print("   - Unstable params (high CV) → Potentially overfit to noise")
    print("4. Validation >> Test suggests overfitting to in-sample period")
    print("5. Use 'rolling' windows for stable regimes, 'expanding' for evolving markets")
    print()
    print("Walk-forward optimization complete!")


if __name__ == "__main__":
    main()
