"""Portfolio Allocator Tutorial: Multi-Strategy Management.

This tutorial demonstrates how to use the PortfolioAllocator to manage
multiple trading strategies with isolated capital allocation.

Example: 3-Strategy Diversified Equity Portfolio
- Long Equity (40%): Buy and hold quality stocks
- Short Equity (30%): Short overvalued stocks
- Market Neutral (30%): Long/short beta-neutral
"""

from decimal import Decimal

import pandas as pd
import structlog

from rustybt.portfolio.allocator import PortfolioAllocator

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

logger = structlog.get_logger()


# Example Strategy Implementations
class LongEquityStrategy:
    """Example long-only equity strategy.

    Strategy: Buy and hold large cap growth stocks.
    """

    def __init__(self):
        self.name = "Long Equity Strategy"
        self.positions_initialized = False

    def handle_data(self, ledger, data):
        """Execute long equity strategy logic.

        Args:
            ledger: DecimalLedger instance for this strategy
            data: Market data for current bar
        """
        # Simple buy-and-hold logic
        # In real implementation, would analyze data and place orders
        if not self.positions_initialized and ledger.cash > Decimal("0"):
            logger.info(
                "long_equity_initializing",
                cash=str(ledger.cash),
                message="Would buy quality large cap stocks",
            )
            self.positions_initialized = True


class ShortEquityStrategy:
    """Example short-only equity strategy.

    Strategy: Short overvalued momentum stocks.
    """

    def __init__(self):
        self.name = "Short Equity Strategy"
        self.positions_initialized = False

    def handle_data(self, ledger, data):
        """Execute short equity strategy logic.

        Args:
            ledger: DecimalLedger instance for this strategy
            data: Market data for current bar
        """
        # Simple short strategy logic
        if not self.positions_initialized and ledger.cash > Decimal("0"):
            logger.info(
                "short_equity_initializing",
                cash=str(ledger.cash),
                message="Would short overvalued stocks",
            )
            self.positions_initialized = True


class MarketNeutralStrategy:
    """Example market-neutral equity strategy.

    Strategy: Long undervalued, short overvalued (beta-neutral).
    """

    def __init__(self):
        self.name = "Market Neutral Strategy"
        self.positions_initialized = False

    def handle_data(self, ledger, data):
        """Execute market neutral strategy logic.

        Args:
            ledger: DecimalLedger instance for this strategy
            data: Market data for current bar
        """
        # Simple market-neutral logic
        if not self.positions_initialized and ledger.cash > Decimal("0"):
            logger.info(
                "market_neutral_initializing",
                cash=str(ledger.cash),
                message="Would establish beta-neutral positions",
            )
            self.positions_initialized = True


def create_diversified_portfolio():
    """Create a 3-strategy diversified portfolio.

    Returns:
        Configured PortfolioAllocator instance
    """
    # Initialize portfolio with $1M
    portfolio = PortfolioAllocator(
        total_capital=Decimal("1000000.00"), name="Diversified Equity Portfolio"
    )

    logger.info(
        "portfolio_created",
        total_capital="$1,000,000",
        message="Creating diversified 3-strategy portfolio",
    )

    # Add long equity strategy (40%)
    long_strategy = LongEquityStrategy()
    portfolio.add_strategy(
        strategy_id="long_equity",
        strategy=long_strategy,
        allocation_pct=Decimal("0.40"),
        metadata={"description": "Long-only large cap growth", "target_beta": 1.0},
    )

    # Add short equity strategy (30%)
    short_strategy = ShortEquityStrategy()
    portfolio.add_strategy(
        strategy_id="short_equity",
        strategy=short_strategy,
        allocation_pct=Decimal("0.30"),
        metadata={"description": "Short overvalued momentum stocks", "target_beta": -1.0},
    )

    # Add market neutral strategy (30%)
    neutral_strategy = MarketNeutralStrategy()
    portfolio.add_strategy(
        strategy_id="market_neutral",
        strategy=neutral_strategy,
        allocation_pct=Decimal("0.30"),
        metadata={"description": "Beta-neutral long/short value", "target_beta": 0.0},
    )

    logger.info(
        "portfolio_configured",
        strategies={
            "long_equity": "40%",
            "short_equity": "30%",
            "market_neutral": "30%",
        },
        allocated_capital=str(portfolio.allocated_capital),
        unallocated=str(portfolio.total_capital - portfolio.allocated_capital),
    )

    return portfolio


def run_portfolio_simulation(portfolio, num_days=100):
    """Run portfolio simulation over time.

    Args:
        portfolio: PortfolioAllocator instance
        num_days: Number of trading days to simulate
    """
    logger.info("simulation_starting", num_days=num_days)

    start_date = pd.Timestamp("2023-01-01")

    for day in range(num_days):
        timestamp = start_date + pd.Timedelta(days=day)

        # Mock market data (in real scenario, would fetch from data source)
        data = {
            "AAPL": {"price": Decimal("150.00") + Decimal(str(day * 0.5))},
            "GOOGL": {"price": Decimal("100.00") + Decimal(str(day * 0.3))},
            "MSFT": {"price": Decimal("300.00") + Decimal(str(day * 0.8))},
        }

        # Execute bar for all strategies
        portfolio.execute_bar(timestamp, data)

        # Log progress every 10 days
        if (day + 1) % 10 == 0:
            metrics = portfolio.get_portfolio_metrics()
            logger.info(
                "simulation_progress",
                day=day + 1,
                total_value=metrics["total_value"],
                portfolio_return=metrics["portfolio_return"],
                active_strategies=metrics["active_strategies"],
            )

    logger.info("simulation_complete", total_days=num_days)


def demonstrate_rebalancing(portfolio):
    """Demonstrate portfolio rebalancing.

    Args:
        portfolio: PortfolioAllocator instance
    """
    logger.info("rebalancing_demonstration", message="Adjusting allocations based on performance")

    # Get current strategy metrics
    strategy_metrics = portfolio.get_strategy_metrics()

    logger.info(
        "current_allocations",
        long_equity=strategy_metrics["long_equity"]["return_pct"],
        short_equity=strategy_metrics["short_equity"]["return_pct"],
        market_neutral=strategy_metrics["market_neutral"]["return_pct"],
    )

    # Rebalance: increase allocation to best performer
    # In real scenario, would use sophisticated allocation algorithm
    new_allocations = {
        "long_equity": Decimal("0.50"),  # Increase from 40%
        "short_equity": Decimal("0.25"),  # Decrease from 30%
        "market_neutral": Decimal("0.25"),  # Decrease from 30%
    }

    portfolio.rebalance(new_allocations, reason="Performance-based rebalancing")

    logger.info(
        "rebalancing_complete",
        new_allocations={k: f"{float(v):.1%}" for k, v in new_allocations.items()},
    )


def demonstrate_dynamic_strategy_management(portfolio):
    """Demonstrate adding and removing strategies dynamically.

    Args:
        portfolio: PortfolioAllocator instance
    """
    logger.info("dynamic_management_demonstration", message="Adding new strategy during runtime")

    # Add a new strategy
    class MomentumStrategy:
        """Simple momentum strategy."""

        def handle_data(self, ledger, data):
            pass

    momentum_strategy = MomentumStrategy()
    portfolio.add_strategy(
        strategy_id="momentum",
        strategy=momentum_strategy,
        allocation_pct=Decimal("0.10"),
        metadata={"description": "Trend-following momentum"},
    )

    logger.info("strategy_added", strategy_id="momentum", allocation="10%")

    # Pause a strategy
    portfolio.pause_strategy("short_equity")
    logger.info("strategy_paused", strategy_id="short_equity")

    # Resume the strategy
    portfolio.resume_strategy("short_equity")
    logger.info("strategy_resumed", strategy_id="short_equity")

    # Remove the momentum strategy
    returned_capital = portfolio.remove_strategy("momentum", liquidate=True)
    logger.info("strategy_removed", strategy_id="momentum", capital_returned=str(returned_capital))


def display_final_results(portfolio):
    """Display final portfolio results.

    Args:
        portfolio: PortfolioAllocator instance
    """
    logger.info("final_results", message="Portfolio Performance Summary")

    # Portfolio-level metrics
    portfolio_metrics = portfolio.get_portfolio_metrics()
    logger.info(
        "portfolio_metrics",
        total_value=portfolio_metrics["total_value"],
        portfolio_return=portfolio_metrics["portfolio_return"],
        num_strategies=portfolio_metrics["num_strategies"],
        weighted_avg_sharpe=portfolio_metrics["weighted_avg_sharpe"],
    )

    # Per-strategy metrics
    strategy_metrics = portfolio.get_strategy_metrics()
    for strategy_id, metrics in strategy_metrics.items():
        logger.info(
            "strategy_performance",
            strategy_id=strategy_id,
            return_pct=metrics["return_pct"],
            sharpe_ratio=metrics["sharpe_ratio"],
            max_drawdown=metrics["max_drawdown"],
            win_rate=metrics["win_rate"],
        )

    # Correlation matrix
    corr_matrix = portfolio.get_correlation_matrix()
    if corr_matrix is not None:
        logger.info("correlation_matrix", message="Strategy return correlations")
        logger.info("correlations", data=corr_matrix.to_dict())


def main():
    """Run the complete portfolio allocator tutorial."""
    logger.info("tutorial_starting", message="Portfolio Allocator Tutorial")

    # Step 1: Create diversified portfolio
    logger.info("step_1", message="Creating 3-strategy diversified portfolio")
    portfolio = create_diversified_portfolio()

    # Step 2: Run simulation
    logger.info("step_2", message="Running 100-day simulation")
    run_portfolio_simulation(portfolio, num_days=100)

    # Step 3: Demonstrate rebalancing
    logger.info("step_3", message="Demonstrating portfolio rebalancing")
    demonstrate_rebalancing(portfolio)

    # Step 4: Demonstrate dynamic strategy management
    logger.info("step_4", message="Demonstrating dynamic strategy management")
    demonstrate_dynamic_strategy_management(portfolio)

    # Step 5: Display final results
    logger.info("step_5", message="Displaying final results")
    display_final_results(portfolio)

    logger.info("tutorial_complete", message="Portfolio Allocator Tutorial Complete")


if __name__ == "__main__":
    main()
