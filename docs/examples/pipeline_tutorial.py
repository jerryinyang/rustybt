#!/usr/bin/env python
#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Example: Pipeline API Tutorial

This example demonstrates how to use the Pipeline API for factor-based
trading strategies and quantitative research.

Key Concepts Demonstrated:
- Creating custom factors
- Building pipelines with filters
- Screening assets based on factors
- Rebalancing based on rankings
- Statistical arbitrage strategies

Usage:
    python examples/pipeline_tutorial.py

Note: Pipeline API is an advanced feature primarily for factor-based strategies.
      For simple strategies, use the standard TradingAlgorithm API.
"""

from rustybt import TradingAlgorithm
from rustybt.pipeline import CustomFactor, Pipeline
from rustybt.pipeline.data import USEquityPricing
from rustybt.pipeline.factors import RSI, Returns, SimpleMovingAverage

print("=" * 70)
print("Pipeline API Tutorial")
print("=" * 70)
print("\nThe Pipeline API allows you to define factor-based strategies")
print("that screen and rank assets based on computed factors.")


# ============================================================================
# Example 1: Basic Pipeline with Built-in Factors
# ============================================================================


def example_1_basic_pipeline():
    """Example 1: Basic pipeline with moving averages and RSI."""
    print("\n" + "=" * 70)
    print("Example 1: Basic Pipeline - Moving Averages & RSI")
    print("=" * 70)

    # Define a pipeline
    def make_pipeline():
        # Get closing prices
        close = USEquityPricing.close.latest

        # Compute factors
        sma_50 = SimpleMovingAverage(inputs=[close], window_length=50)
        sma_200 = SimpleMovingAverage(inputs=[close], window_length=200)
        rsi_14 = RSI(inputs=[close], window_length=14)

        # Create filters
        price_above_sma50 = close > sma_50
        uptrend = sma_50 > sma_200
        oversold = rsi_14 < 30

        # Combine filters (bullish stocks that are oversold)
        screen = price_above_sma50 & uptrend & oversold

        # Build pipeline
        return Pipeline(
            columns={
                "close": close,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "rsi_14": rsi_14,
            },
            screen=screen,
        )

    print("\n✓ Pipeline defined")
    print("\nFactors:")
    print("  - SMA(50): 50-day simple moving average")
    print("  - SMA(200): 200-day simple moving average")
    print("  - RSI(14): 14-day Relative Strength Index")
    print("\nScreen:")
    print("  - Price > SMA(50)")
    print("  - SMA(50) > SMA(200) (golden cross)")
    print("  - RSI < 30 (oversold)")


# ============================================================================
# Example 2: Custom Factor
# ============================================================================


def example_2_custom_factor():
    """Example 2: Creating a custom factor."""
    print("\n" + "=" * 70)
    print("Example 2: Custom Factor - Mean Reversion Score")
    print("=" * 70)

    class MeanReversionScore(CustomFactor):
        """Custom factor: Mean reversion score.

        Measures how far price is from its N-day average,
        normalized by volatility (z-score).
        """

        inputs = [USEquityPricing.close]
        window_length = 20

        def compute(self, today, assets, out, close):
            """Compute mean reversion score.

            Args:
                today: Current date
                assets: Assets being computed
                out: Output array to fill
                close: Close price array (window_length x num_assets)
            """
            # Calculate rolling mean and std
            mean = close.mean(axis=0)
            std = close.std(axis=0)

            # Calculate z-score (current price vs mean)
            current_price = close[-1]
            z_score = (current_price - mean) / std

            # Return negative z-score (more negative = more oversold = higher score)
            out[:] = -z_score

    # Use custom factor in pipeline
    def make_pipeline():
        close = USEquityPricing.close.latest
        mean_reversion = MeanReversionScore()

        # Buy top decile (most oversold)
        top_oversold = mean_reversion.top(10, mask=close > 10)

        return Pipeline(
            columns={
                "close": close,
                "mean_reversion_score": mean_reversion,
            },
            screen=top_oversold,
        )

    print("\n✓ Custom factor created")
    print("\nMean Reversion Score:")
    print("  - Measures price deviation from 20-day average")
    print("  - Normalized by volatility (z-score)")
    print("  - Higher score = more oversold = better buy opportunity")


# ============================================================================
# Example 3: Pipeline in Trading Algorithm
# ============================================================================


def example_3_pipeline_in_algorithm():
    """Example 3: Using pipeline in a trading algorithm."""
    print("\n" + "=" * 70)
    print("Example 3: Pipeline-Based Trading Strategy")
    print("=" * 70)

    class MomentumPipelineStrategy(TradingAlgorithm):
        """Strategy that uses pipeline for stock selection."""

        def initialize(self):
            """Initialize strategy and attach pipeline."""
            # Create pipeline
            pipe = self.make_pipeline()

            # Attach pipeline to algorithm
            self.attach_pipeline(pipe, "momentum_screen")

            # Schedule rebalance
            self.schedule_function(
                self.rebalance,
                date_rule=self.date_rules.month_start(),
                time_rule=self.time_rules.market_open(),
            )

        def make_pipeline(self):
            """Define screening pipeline."""
            close = USEquityPricing.close.latest

            # Momentum factors
            returns_1m = Returns(window_length=21)
            returns_3m = Returns(window_length=63)
            returns_6m = Returns(window_length=126)

            # Combined momentum score (equal weight)
            momentum_score = (returns_1m + returns_3m + returns_6m) / 3

            # Universe filter (liquid stocks)
            volume = USEquityPricing.volume.latest
            dollar_volume = close * volume
            liquid = dollar_volume.top(500)

            # Select top 50 momentum stocks
            top_momentum = momentum_score.top(50, mask=liquid)

            return Pipeline(
                columns={
                    "close": close,
                    "momentum_score": momentum_score,
                    "returns_1m": returns_1m,
                    "returns_3m": returns_3m,
                    "returns_6m": returns_6m,
                },
                screen=top_momentum,
            )

        def rebalance(self, context, data):
            """Rebalance portfolio based on pipeline output."""
            # Get pipeline output
            pipeline_output = self.pipeline_output("momentum_screen")

            # Get current positions
            current_positions = set(context.portfolio.positions.keys())

            # Get target positions from pipeline
            target_positions = set(pipeline_output.index)

            # Close positions no longer in screen
            for asset in current_positions - target_positions:
                self.order_target_percent(asset, 0)

            # Equal weight new positions
            if len(target_positions) > 0:
                target_weight = 1.0 / len(target_positions)

                for asset in target_positions:
                    self.order_target_percent(asset, target_weight)

    print("\n✓ Pipeline-based strategy defined")
    print("\nStrategy Logic:")
    print("  1. Screen universe to top 500 liquid stocks")
    print("  2. Calculate momentum score (1m, 3m, 6m returns)")
    print("  3. Select top 50 momentum stocks")
    print("  4. Rebalance monthly to equal-weight portfolio")
    print("\nThis is a typical quantitative momentum strategy!")


# ============================================================================
# Example 4: Advanced Filters and Classifiers
# ============================================================================


def example_4_advanced_filters():
    """Example 4: Advanced filters and classifiers."""
    print("\n" + "=" * 70)
    print("Example 4: Advanced Filters - Sector Neutral Strategy")
    print("=" * 70)

    def make_pipeline():
        close = USEquityPricing.close.latest
        volume = USEquityPricing.volume.latest

        # Momentum factor
        returns_3m = Returns(window_length=63)

        # Universe: liquid stocks
        dollar_volume = close * volume
        liquid = dollar_volume.percentile_between(80, 100)

        # Sector classifier (would need sector data)
        # sector = Sector()

        # Select top 3 momentum stocks per sector
        # This creates a sector-neutral portfolio
        # top_per_sector = returns_3m.top(3, groupby=sector, mask=liquid)

        # For this example, just use top momentum overall
        top_momentum = returns_3m.top(20, mask=liquid)

        return Pipeline(
            columns={
                "close": close,
                "returns_3m": returns_3m,
                # 'sector': sector,
            },
            screen=top_momentum,
        )

    print("\n✓ Advanced pipeline defined")
    print("\nAdvanced Features:")
    print("  - Percentile filters (top 20% by dollar volume)")
    print("  - Sector classification (requires sector data)")
    print("  - Groupby operations (sector-neutral selection)")
    print("  - Multiple filter combinations")


# ============================================================================
# Example 5: Pipeline Performance Tips
# ============================================================================


def example_5_performance_tips():
    """Example 5: Pipeline performance optimization."""
    print("\n" + "=" * 70)
    print("Example 5: Pipeline Performance Tips")
    print("=" * 70)

    print("\n💡 Performance Optimization Tips:")
    print("\n1. Universe Reduction:")
    print("   - Filter to tradable universe early (e.g., top 1000 by volume)")
    print("   - Reduces computation for subsequent factors")

    print("\n2. Factor Caching:")
    print("   - Factors are computed once per day and cached")
    print("   - Reuse factors across multiple pipelines")

    print("\n3. Window Length:")
    print("   - Longer windows = more memory usage")
    print("   - Use minimum required window length")

    print("\n4. Custom Factors:")
    print("   - Implement compute() efficiently")
    print("   - Use NumPy vectorized operations")
    print("   - Avoid Python loops over assets")

    print("\n5. Polars Integration:")
    print("   - RustyBT uses Polars for data engine")
    print("   - Factors automatically benefit from Polars performance")
    print("   - 5-10x faster than pandas-based implementations")


# ============================================================================
# Example 6: Pipeline Debugging
# ============================================================================


def example_6_debugging():
    """Example 6: Pipeline debugging techniques."""
    print("\n" + "=" * 70)
    print("Example 6: Pipeline Debugging")
    print("=" * 70)

    print("\n🔧 Debugging Techniques:")

    print("\n1. Inspect Pipeline Output:")
    print("   pipeline_output = algo.pipeline_output('my_pipeline')")
    print("   print(pipeline_output.head())")

    print("\n2. Check Factor Values:")
    print("   print(pipeline_output['momentum_score'].describe())")
    print("   print(pipeline_output['momentum_score'].hist())")

    print("\n3. Validate Screen:")
    print("   screen_count = len(pipeline_output)")
    print("   print(f'Screen passed: {screen_count} assets')")

    print("\n4. Test Factors Independently:")
    print("   # Run pipeline without screen to see all factor values")
    print("   pipe = Pipeline(columns={'factor': my_factor})")

    print("\n5. Compare to Benchmark:")
    print("   # Compare your factor to known factors (e.g., momentum)")
    print("   correlation = pipe_output['my_factor'].corr(pipe_output['momentum'])")


# ============================================================================
# Run All Examples
# ============================================================================


def main():
    """Run all pipeline tutorial examples."""
    try:
        example_1_basic_pipeline()
        example_2_custom_factor()
        example_3_pipeline_in_algorithm()
        example_4_advanced_filters()
        example_5_performance_tips()
        example_6_debugging()

        print("\n" + "=" * 70)
        print("✨ Pipeline Tutorial Complete!")
        print("=" * 70)

        print("\n📚 Key Takeaways:")
        print("  1. Pipelines enable factor-based strategies")
        print("  2. Built-in factors: SMA, RSI, Returns, etc.")
        print("  3. Custom factors: Inherit from CustomFactor")
        print("  4. Filters and screens: Select tradable universe")
        print("  5. Integration: Use with TradingAlgorithm")

        print("\n🎯 When to Use Pipeline:")
        print("  ✓ Factor-based strategies (momentum, value, quality)")
        print("  ✓ Statistical arbitrage")
        print("  ✓ Quantitative research and backtesting")
        print("  ✓ Multi-asset screening and ranking")
        print("  ✗ Simple technical indicator strategies (use regular API)")

        print("\n📖 Next Steps:")
        print("  1. Read: docs/guides/pipeline-api-guide.md")
        print("  2. Try: Implement your own custom factor")
        print("  3. Backtest: Run a momentum strategy with pipeline")
        print("  4. Research: Use pipeline for factor research")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
