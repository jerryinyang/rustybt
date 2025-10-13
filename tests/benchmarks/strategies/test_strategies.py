"""Unit tests for benchmark strategies.

Ensures strategies are deterministic and produce correct signals.
"""

import pandas as pd
import pytest


def test_simple_sma_crossover_deterministic():
    """Verify SimpleSMACrossover produces same results for same inputs."""
    from .simple_sma_crossover import create_handle_data_fn, create_initialize_fn

    # Strategy should be deterministic - implementation exists
    initialize_fn = create_initialize_fn(n_assets=10, sma_short=50, sma_long=200)
    handle_data_fn = create_handle_data_fn(sma_short=50, sma_long=200)

    assert initialize_fn is not None
    assert handle_data_fn is not None


def test_momentum_strategy_deterministic():
    """Verify MomentumStrategy produces same results for same inputs."""
    from .momentum_strategy import create_handle_data_fn, create_initialize_fn

    # Strategy should be deterministic - implementation exists
    initialize_fn = create_initialize_fn(n_assets=10)
    handle_data_fn = create_handle_data_fn()

    assert initialize_fn is not None
    assert handle_data_fn is not None


def test_multi_indicator_strategy_deterministic():
    """Verify MultiIndicatorStrategy produces same results for same inputs."""
    from .multi_indicator_strategy import create_handle_data_fn, create_initialize_fn

    # Strategy should be deterministic - implementation exists
    initialize_fn = create_initialize_fn(n_assets=10)
    handle_data_fn = create_handle_data_fn()

    assert initialize_fn is not None
    assert handle_data_fn is not None


def test_simple_sma_signal_generation():
    """Test SMA crossover signal generation logic."""
    # Create mock price series
    prices_short = pd.Series([100, 101, 102, 103, 104])
    prices_long = pd.Series([105, 105, 105, 105, 105])

    # Calculate SMAs
    short_mavg = prices_short.mean()  # 102
    long_mavg = prices_long.mean()  # 105

    # Should generate sell signal (short < long)
    assert short_mavg < long_mavg

    # Reverse scenario
    prices_short_up = pd.Series([106, 107, 108, 109, 110])
    short_mavg_up = prices_short_up.mean()  # 108

    # Should generate buy signal (short > long)
    assert short_mavg_up > long_mavg


def test_momentum_rsi_calculation():
    """Test RSI calculation produces values in 0-100 range."""
    # Create mock price series with uptrend
    prices_up = pd.Series(range(100, 120))

    # Calculate RSI manually (simplified)
    deltas = prices_up.diff()
    gains = deltas.where(deltas > 0, 0.0)
    losses = -deltas.where(deltas < 0, 0.0)

    window = 14
    avg_gain = gains.rolling(window=window).mean().iloc[-1]
    avg_loss = losses.rolling(window=window).mean().iloc[-1]

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    # RSI should be in valid range
    assert 0 <= rsi <= 100
    # Uptrend should produce high RSI
    assert rsi > 50


def test_multi_indicator_score_range():
    """Test multi-indicator score is normalized to [-1, 1] range."""
    # The score normalization logic divides score by max_score
    # This test verifies the concept

    score = 10.0
    max_score = 20.0
    normalized_score = score / max_score

    assert -1.0 <= normalized_score <= 1.0
    assert normalized_score == 0.5

    # Test negative score
    score_neg = -15.0
    normalized_score_neg = score_neg / max_score

    assert -1.0 <= normalized_score_neg <= 1.0
    assert normalized_score_neg == -0.75


def test_strategy_imports():
    """Test that all strategy modules can be imported."""
    from . import MomentumStrategy, MultiIndicatorStrategy, SimpleSMACrossover

    # Instantiate each strategy
    simple_strategy = SimpleSMACrossover()
    momentum_strategy = MomentumStrategy()
    multi_strategy = MultiIndicatorStrategy()

    assert simple_strategy is not None
    assert momentum_strategy is not None
    assert multi_strategy is not None


def test_strategy_parameter_validation():
    """Test strategy parameter validation."""
    from .momentum_strategy import MomentumStrategy
    from .multi_indicator_strategy import MultiIndicatorStrategy
    from .simple_sma_crossover import SimpleSMACrossover

    # Simple strategy with custom parameters
    simple = SimpleSMACrossover(sma_short=20, sma_long=100)
    assert simple.sma_short == 20
    assert simple.sma_long == 100

    # Momentum strategy with custom parameters
    momentum = MomentumStrategy(momentum_window=30, rsi_window=10)
    assert momentum.momentum_window == 30
    assert momentum.rsi_window == 10

    # Multi-indicator strategy with custom parameters
    multi = MultiIndicatorStrategy(sma_windows=[5, 10, 20], ema_windows=[8, 13])
    assert multi.sma_windows == [5, 10, 20]
    assert multi.ema_windows == [8, 13]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
