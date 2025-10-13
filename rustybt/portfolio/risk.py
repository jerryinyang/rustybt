"""Portfolio-level risk management with comprehensive limit enforcement.

This module provides portfolio-level risk management capabilities including:
- Position limits (leverage, concentration)
- Drawdown limits with trading halt
- Volatility targeting
- Real-time risk metrics (VaR, beta, correlation)
- Pre-trade risk checks
- Risk limit violation handling
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import structlog

logger = structlog.get_logger()


class RiskLimitType(Enum):
    """Types of risk limits."""

    LEVERAGE = "leverage"
    CONCENTRATION = "concentration"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    VAR = "var"
    CORRELATION = "correlation"


class RiskAction(Enum):
    """Actions taken on risk limit violations."""

    ALLOW = "allow"  # No violation
    WARN = "warn"  # Warning level violation
    REDUCE = "reduce"  # Reduce position size
    REJECT = "reject"  # Reject order
    HALT = "halt"  # Halt all trading


@dataclass
class RiskLimits:
    """Risk limit configuration.

    Hedge Fund Style Limits Example:
    ================================
    - Max Leverage: 2.0x (conservative fund) to 6.0x (aggressive fund)
    - Max Single Asset Exposure: 15-25% of portfolio
    - Max Drawdown: 15-20% from peak
    - Target Volatility: 10-15% annualized
    - Max VaR (95%): 3-5% of portfolio per day
    - Max Correlation: 0.8 (reduce allocation if strategies too correlated)
    """

    # Leverage limits
    max_portfolio_leverage: Decimal = field(default_factory=lambda: Decimal("2.0"))  # 2x leverage
    warn_portfolio_leverage: Decimal = field(default_factory=lambda: Decimal("1.8"))  # 1.8x warning

    # Concentration limits
    max_single_asset_exposure: Decimal = field(
        default_factory=lambda: Decimal("0.20")
    )  # 20% per asset
    warn_single_asset_exposure: Decimal = field(
        default_factory=lambda: Decimal("0.15")
    )  # 15% warning

    # Drawdown limits
    max_drawdown: Decimal = field(default_factory=lambda: Decimal("0.15"))  # 15% max drawdown
    warn_drawdown: Decimal = field(default_factory=lambda: Decimal("0.10"))  # 10% warning
    halt_drawdown: Decimal = field(default_factory=lambda: Decimal("0.20"))  # 20% halt trading

    # Volatility limits
    target_volatility: Decimal | None = field(default_factory=lambda: Decimal("0.12"))  # 12% target
    max_volatility: Decimal | None = field(default_factory=lambda: Decimal("0.20"))  # 20% max

    # VaR limits (Value at Risk)
    max_var_pct: Decimal = field(default_factory=lambda: Decimal("0.05"))  # 5% max daily VaR
    var_confidence_level: Decimal = field(default_factory=lambda: Decimal("0.95"))  # 95% confidence

    # Correlation limits
    max_strategy_correlation: Decimal = field(
        default_factory=lambda: Decimal("0.80")
    )  # 0.8 max correlation

    # Trading halt flag
    trading_halted: bool = field(default=False)

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"RiskLimits(leverage={self.max_portfolio_leverage}, "
            f"concentration={self.max_single_asset_exposure}, "
            f"drawdown={self.max_drawdown}, "
            f"target_vol={self.target_volatility})"
        )


@dataclass
class RiskMetrics:
    """Real-time risk metrics for portfolio.

    Metrics:
    ========
    - Leverage: Total exposure / Total equity
    - Concentration: Max single asset exposure
    - Drawdown: (Current value - Peak value) / Peak value
    - Volatility: Annualized standard deviation of returns
    - VaR: Value at Risk at confidence level
    - Beta: Portfolio beta against market index
    - Correlation: Strategy correlation matrix
    """

    timestamp: pd.Timestamp

    # Leverage metrics
    total_exposure: Decimal
    total_equity: Decimal
    leverage: Decimal

    # Concentration metrics
    max_asset_exposure: Decimal

    # Drawdown metrics
    current_value: Decimal
    peak_value: Decimal
    current_drawdown: Decimal
    max_drawdown: Decimal

    # Volatility metrics
    portfolio_volatility: Decimal  # Annualized

    # VaR metrics
    var_95: Decimal  # 95% confidence VaR
    var_99: Decimal  # 99% confidence VaR

    # Optional fields (must come after required fields)
    max_asset_symbol: str | None = None
    portfolio_beta: Decimal | None = None
    avg_strategy_correlation: Decimal | None = None
    max_strategy_correlation: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for logging."""
        return {
            "timestamp": str(self.timestamp),
            "leverage": f"{float(self.leverage):.2f}x",
            "max_asset_exposure": f"{float(self.max_asset_exposure):.1%}",
            "max_asset": self.max_asset_symbol,
            "current_drawdown": f"{float(self.current_drawdown):.2%}",
            "max_drawdown": f"{float(self.max_drawdown):.2%}",
            "volatility": f"{float(self.portfolio_volatility):.1%}",
            "var_95": f"${float(self.var_95):,.2f}",
            "var_99": f"${float(self.var_99):,.2f}",
            "beta": f"{float(self.portfolio_beta):.2f}" if self.portfolio_beta else None,
            "avg_correlation": (
                f"{float(self.avg_strategy_correlation):.2f}"
                if self.avg_strategy_correlation
                else None
            ),
        }


class RiskManager:
    """Portfolio-level risk manager.

    Risk Management Flow:
    ====================

    1. Pre-Trade Risk Check (before order execution):
       - Check leverage limit: would order exceed max leverage?
       - Check concentration limit: would order exceed max asset exposure?
       - Check drawdown limit: is portfolio in halt state?
       - Return: (allowed: bool, action: RiskAction, reason: str)

    2. Real-Time Metrics Update (after each bar):
       - Calculate portfolio leverage
       - Calculate asset concentration
       - Calculate drawdown from peak
       - Calculate portfolio volatility
       - Calculate VaR (Historical Simulation)
       - Calculate correlation matrix
       - Calculate portfolio beta
       - Log metrics and check limits

    3. Limit Violation Handling:
       - WARN: Log warning, allow trade
       - REDUCE: Reduce position size to stay within limit
       - REJECT: Reject order entirely
       - HALT: Stop all trading, liquidate if necessary

    4. Volatility Targeting (optional):
       - Calculate current portfolio volatility
       - If volatility > target: reduce allocations
       - If volatility < target: increase allocations
       - Rebalance to maintain target volatility

    Mathematical Formulas:
    =====================

    Leverage:
        L = (Σ|position_value_i|) / total_equity

    Concentration:
        C_asset = (Σ|position_value_i| for positions in asset) / total_equity

    Drawdown:
        DD = (current_value - peak_value) / peak_value

    Volatility (annualized):
        σ_annual = std(daily_returns) × √252

    VaR (Historical Simulation at confidence α):
        VaR_α = -percentile(returns, 1-α) × portfolio_value
        Example: VaR_95 = -percentile(returns, 0.05) × portfolio_value

    Correlation (Pearson):
        ρ(X,Y) = Cov(X,Y) / (σ_X × σ_Y)
        Where:
            Cov(X,Y) = E[(X - μ_X)(Y - μ_Y)]
            σ_X = std(X)

    Beta (against market index):
        β = Cov(portfolio_returns, market_returns) / Var(market_returns)

    Volatility Targeting:
        target_allocation_i = current_allocation_i × (target_vol / current_vol)
    """

    def __init__(
        self,
        limits: RiskLimits | None = None,
        lookback_window: int = 252,  # 1 year for metrics
    ):
        """Initialize risk manager.

        Args:
            limits: Risk limits configuration (uses defaults if None)
            lookback_window: Number of periods for metrics calculation
        """
        self.limits = limits or RiskLimits()
        self.lookback_window = lookback_window

        # Metrics history
        self.metrics_history: list[RiskMetrics] = []

        # Violation tracking
        self.violation_count: dict[RiskLimitType, int] = dict.fromkeys(RiskLimitType, 0)

        logger.info(
            "risk_manager_initialized", limits=str(self.limits), lookback_window=lookback_window
        )

    def check_order(
        self,
        portfolio: Any,
        order: Any,
        current_prices: dict[str, Decimal],  # Order object
    ) -> tuple[bool, RiskAction, str]:
        """Pre-trade risk check for order.

        Args:
            portfolio: PortfolioAllocator instance
            order: Order to check
            current_prices: Current market prices

        Returns:
            Tuple of (allowed, action, reason)
        """
        # Check if trading halted
        if self.limits.trading_halted:
            logger.warning(
                "order_rejected_trading_halted", order_id=order.id, asset=order.asset.symbol
            )
            return False, RiskAction.HALT, "Trading halted due to risk limits"

        # Track warnings
        warnings = []

        # Check leverage limit
        allowed, action, reason = self._check_leverage_limit(portfolio, order, current_prices)
        if not allowed:
            self.violation_count[RiskLimitType.LEVERAGE] += 1
            return allowed, action, reason
        if action == RiskAction.WARN:
            warnings.append((action, reason))

        # Check concentration limit
        allowed, action, reason = self._check_concentration_limit(portfolio, order, current_prices)
        if not allowed:
            self.violation_count[RiskLimitType.CONCENTRATION] += 1
            return allowed, action, reason
        if action == RiskAction.WARN:
            warnings.append((action, reason))

        # Check drawdown limit
        allowed, action, reason = self._check_drawdown_limit(portfolio)
        if not allowed:
            self.violation_count[RiskLimitType.DRAWDOWN] += 1
            return allowed, action, reason
        if action == RiskAction.WARN:
            warnings.append((action, reason))

        # If there are warnings, return first warning
        if warnings:
            return True, warnings[0][0], warnings[0][1]

        # All checks passed
        return True, RiskAction.ALLOW, "Order passes all risk checks"

    def _check_leverage_limit(
        self, portfolio: Any, order: Any, current_prices: dict[str, Decimal]
    ) -> tuple[bool, RiskAction, str]:
        """Check if order would exceed leverage limit.

        Formula:
            new_leverage = (total_exposure + order_exposure) / total_equity
        """
        # Calculate current total equity
        total_equity = portfolio.get_total_portfolio_value()

        # Calculate current total exposure (sum of absolute position values)
        total_exposure = self._calculate_total_exposure(portfolio, current_prices)

        # Calculate order exposure
        order_price = current_prices.get(order.asset.symbol, order.estimated_fill_price)
        order_exposure = abs(order.amount) * order_price

        # Calculate new leverage
        new_exposure = total_exposure + order_exposure
        new_leverage = new_exposure / total_equity if total_equity > Decimal("0") else Decimal("0")

        # Check against limits
        if new_leverage > self.limits.max_portfolio_leverage:
            logger.warning(
                "leverage_limit_exceeded",
                order_id=order.id,
                asset=order.asset.symbol,
                current_leverage=f"{float(new_leverage):.2f}x",
                max_leverage=f"{float(self.limits.max_portfolio_leverage):.2f}x",
            )
            max_lev = float(self.limits.max_portfolio_leverage)
            return (
                False,
                RiskAction.REJECT,
                f"Leverage limit exceeded: {float(new_leverage):.2f}x > {max_lev:.2f}x",
            )

        if new_leverage > self.limits.warn_portfolio_leverage:
            logger.warning(
                "leverage_warning",
                order_id=order.id,
                current_leverage=f"{float(new_leverage):.2f}x",
                warn_leverage=f"{float(self.limits.warn_portfolio_leverage):.2f}x",
            )
            return True, RiskAction.WARN, f"Leverage warning: {float(new_leverage):.2f}x"

        return True, RiskAction.ALLOW, "Leverage check passed"

    def _check_concentration_limit(
        self, portfolio: Any, order: Any, current_prices: dict[str, Decimal]
    ) -> tuple[bool, RiskAction, str]:
        """Check if order would exceed concentration limit.

        Formula:
            asset_exposure = Σ|position_value| for all positions in asset
            concentration = asset_exposure / total_equity
        """
        total_equity = portfolio.get_total_portfolio_value()

        # Calculate current exposure to order asset across all strategies
        asset_exposure = Decimal("0")
        for strategy_alloc in portfolio.strategies.values():
            for position in strategy_alloc.ledger.positions.values():
                if position.asset.symbol == order.asset.symbol:
                    position_value = abs(position.amount) * current_prices.get(
                        position.asset.symbol, position.last_sale_price
                    )
                    asset_exposure += position_value

        # Add order exposure
        order_price = current_prices.get(order.asset.symbol, order.estimated_fill_price)
        order_exposure = abs(order.amount) * order_price
        new_asset_exposure = asset_exposure + order_exposure

        # Calculate concentration percentage
        concentration_pct = (
            new_asset_exposure / total_equity if total_equity > Decimal("0") else Decimal("0")
        )

        # Check against limits
        if concentration_pct > self.limits.max_single_asset_exposure:
            logger.warning(
                "concentration_limit_exceeded",
                order_id=order.id,
                asset=order.asset.symbol,
                concentration=f"{float(concentration_pct):.1%}",
                max_concentration=f"{float(self.limits.max_single_asset_exposure):.1%}",
            )
            max_conc = float(self.limits.max_single_asset_exposure)
            return (
                False,
                RiskAction.REJECT,
                f"Concentration limit exceeded: {float(concentration_pct):.1%} > {max_conc:.1%}",
            )

        if concentration_pct > self.limits.warn_single_asset_exposure:
            logger.warning(
                "concentration_warning",
                order_id=order.id,
                asset=order.asset.symbol,
                concentration=f"{float(concentration_pct):.1%}",
            )
            return True, RiskAction.WARN, f"Concentration warning: {float(concentration_pct):.1%}"

        return True, RiskAction.ALLOW, "Concentration check passed"

    def _check_drawdown_limit(self, portfolio: Any) -> tuple[bool, RiskAction, str]:
        """Check if portfolio drawdown exceeds limit.

        Formula:
            drawdown = (current_value - peak_value) / peak_value
        """
        current_value = portfolio.get_total_portfolio_value()

        # Calculate peak value across all strategies
        peak_value = Decimal("0")
        for strategy_alloc in portfolio.strategies.values():
            peak_value += strategy_alloc.performance.peak_value

        if peak_value == Decimal("0"):
            peak_value = portfolio.total_capital

        # Calculate drawdown
        if peak_value > Decimal("0"):
            current_drawdown = (current_value - peak_value) / peak_value
        else:
            current_drawdown = Decimal("0")

        # Check halt threshold (critical)
        if current_drawdown < -abs(self.limits.halt_drawdown):
            logger.error(
                "drawdown_halt_triggered",
                current_drawdown=f"{float(current_drawdown):.2%}",
                halt_threshold=f"{float(self.limits.halt_drawdown):.2%}",
                action="HALT_ALL_TRADING",
            )
            self.limits.trading_halted = True
            halt_thresh = float(self.limits.halt_drawdown)
            return (
                False,
                RiskAction.HALT,
                f"Trading halted: drawdown {float(current_drawdown):.2%} exceeds {halt_thresh:.2%}",
            )

        # Check max drawdown threshold
        if current_drawdown < -abs(self.limits.max_drawdown):
            logger.error(
                "drawdown_limit_exceeded",
                current_drawdown=f"{float(current_drawdown):.2%}",
                max_drawdown=f"{float(self.limits.max_drawdown):.2%}",
            )
            return (
                False,
                RiskAction.REJECT,
                f"Drawdown limit exceeded: {float(current_drawdown):.2%}",
            )

        # Check warning threshold
        if current_drawdown < -abs(self.limits.warn_drawdown):
            logger.warning(
                "drawdown_warning",
                current_drawdown=f"{float(current_drawdown):.2%}",
                warn_drawdown=f"{float(self.limits.warn_drawdown):.2%}",
            )
            return True, RiskAction.WARN, f"Drawdown warning: {float(current_drawdown):.2%}"

        return True, RiskAction.ALLOW, "Drawdown check passed"

    def _calculate_total_exposure(
        self, portfolio: Any, current_prices: dict[str, Decimal]
    ) -> Decimal:
        """Calculate total exposure across all strategies.

        Formula:
            total_exposure = Σ|position_value_i|
        """
        total_exposure = Decimal("0")

        for strategy_alloc in portfolio.strategies.values():
            for position in strategy_alloc.ledger.positions.values():
                price = current_prices.get(position.asset.symbol, position.last_sale_price)
                position_value = abs(position.amount) * price
                total_exposure += position_value

        return total_exposure

    def calculate_metrics(
        self,
        portfolio: Any,
        current_prices: dict[str, Decimal],
        market_returns: list[Decimal] | None = None,
    ) -> RiskMetrics:
        """Calculate real-time risk metrics for portfolio.

        Args:
            portfolio: PortfolioAllocator instance
            current_prices: Current market prices
            market_returns: Optional market index returns for beta calculation

        Returns:
            RiskMetrics instance
        """
        timestamp = pd.Timestamp.now()

        # Calculate leverage
        total_equity = portfolio.get_total_portfolio_value()
        total_exposure = self._calculate_total_exposure(portfolio, current_prices)
        leverage = total_exposure / total_equity if total_equity > Decimal("0") else Decimal("0")

        # Calculate concentration
        max_asset_exposure, max_asset_symbol = self._calculate_max_concentration(
            portfolio, current_prices, total_equity
        )

        # Calculate drawdown
        current_value = total_equity
        peak_value = Decimal("0")
        for strategy_alloc in portfolio.strategies.values():
            peak_value += strategy_alloc.performance.peak_value

        if peak_value == Decimal("0"):
            peak_value = portfolio.total_capital

        current_drawdown = (
            (current_value - peak_value) / peak_value if peak_value > Decimal("0") else Decimal("0")
        )

        # Calculate max drawdown
        max_drawdown = Decimal("0")
        for strategy_alloc in portfolio.strategies.values():
            if strategy_alloc.performance.max_drawdown < max_drawdown:
                max_drawdown = strategy_alloc.performance.max_drawdown

        # Calculate portfolio volatility
        portfolio_volatility = self._calculate_portfolio_volatility(portfolio)

        # Calculate VaR
        var_95 = self.calculate_var(portfolio, Decimal("0.95"), current_value)
        var_99 = self.calculate_var(portfolio, Decimal("0.99"), current_value)

        # Calculate beta (if market returns provided)
        portfolio_beta = None
        if market_returns:
            portfolio_beta = self._calculate_portfolio_beta(portfolio, market_returns)

        # Calculate strategy correlation
        avg_corr, max_corr = self._calculate_strategy_correlations(portfolio)

        # Create metrics
        metrics = RiskMetrics(
            timestamp=timestamp,
            total_exposure=total_exposure,
            total_equity=total_equity,
            leverage=leverage,
            max_asset_exposure=max_asset_exposure,
            max_asset_symbol=max_asset_symbol,
            current_value=current_value,
            peak_value=peak_value,
            current_drawdown=current_drawdown,
            max_drawdown=max_drawdown,
            portfolio_volatility=portfolio_volatility,
            var_95=var_95,
            var_99=var_99,
            portfolio_beta=portfolio_beta,
            avg_strategy_correlation=avg_corr,
            max_strategy_correlation=max_corr,
        )

        # Store in history
        self.metrics_history.append(metrics)

        # Log metrics
        logger.info("risk_metrics_calculated", **metrics.to_dict())

        return metrics

    def _calculate_max_concentration(
        self, portfolio: Any, current_prices: dict[str, Decimal], total_equity: Decimal
    ) -> tuple[Decimal, str | None]:
        """Calculate maximum single asset concentration."""
        asset_exposures: dict[str, Decimal] = {}

        for strategy_alloc in portfolio.strategies.values():
            for position in strategy_alloc.ledger.positions.values():
                symbol = position.asset.symbol
                price = current_prices.get(symbol, position.last_sale_price)
                position_value = abs(position.amount) * price

                if symbol not in asset_exposures:
                    asset_exposures[symbol] = Decimal("0")
                asset_exposures[symbol] += position_value

        if not asset_exposures:
            return Decimal("0"), None

        max_symbol = max(asset_exposures, key=asset_exposures.get)  # type: ignore
        max_exposure = asset_exposures[max_symbol]
        max_exposure_pct = (
            max_exposure / total_equity if total_equity > Decimal("0") else Decimal("0")
        )

        return max_exposure_pct, max_symbol

    def _calculate_portfolio_volatility(self, portfolio: Any) -> Decimal:
        """Calculate portfolio volatility (annualized).

        Formula:
            σ_portfolio = std(portfolio_returns) × √252
        """
        # Collect portfolio returns (aggregate across strategies)
        # For simplicity, weight by allocation
        if not portfolio.strategies:
            return Decimal("0")

        # Get minimum return length
        min_length = (
            min(
                len(alloc.performance.returns)
                for alloc in portfolio.strategies.values()
                if len(alloc.performance.returns) > 0
            )
            if any(len(alloc.performance.returns) > 0 for alloc in portfolio.strategies.values())
            else 0
        )

        if min_length < 2:
            return Decimal("0")

        # Calculate weighted portfolio returns
        portfolio_returns = []
        for i in range(min_length):
            period_return = Decimal("0")
            total_weight = Decimal("0")

            for alloc in portfolio.strategies.values():
                if i < len(alloc.performance.returns):
                    weight = alloc.allocated_capital / portfolio.total_capital
                    period_return += alloc.performance.returns[i] * weight
                    total_weight += weight

            if total_weight > Decimal("0"):
                portfolio_returns.append(period_return)

        if len(portfolio_returns) < 2:
            return Decimal("0")

        # Calculate standard deviation
        returns_array = np.array([float(r) for r in portfolio_returns])
        std = np.std(returns_array, ddof=1)

        # Annualize (assume daily data, 252 trading days)
        annualized_vol = Decimal(str(std)) * Decimal(str(np.sqrt(252)))

        return annualized_vol

    def calculate_var(
        self, portfolio: Any, confidence_level: Decimal, portfolio_value: Decimal
    ) -> Decimal:
        """Calculate Value at Risk using Historical Simulation.

        Historical Simulation Method:
        ============================
        1. Collect historical returns (e.g., 252 days)
        2. Sort returns from worst to best
        3. Find percentile corresponding to (1 - confidence_level)
        4. VaR = -percentile × portfolio_value

        Example:
            confidence_level = 0.95 (95%)
            percentile_index = 0.05 (5th percentile)
            If 5th percentile return = -2.5%
            VaR_95 = -(-2.5%) × $1,000,000 = $25,000

        Formula:
            VaR_α = -percentile(returns, 1-α) × portfolio_value

        Args:
            portfolio: PortfolioAllocator instance
            confidence_level: Confidence level (0.95 = 95%)
            portfolio_value: Current portfolio value

        Returns:
            VaR amount (positive value representing potential loss)
        """
        # Collect portfolio returns
        returns = self._get_portfolio_returns(portfolio)

        if len(returns) < 10:
            # Insufficient data
            logger.warning(
                "var_calculation_insufficient_data", num_returns=len(returns), min_required=10
            )
            return Decimal("0")

        # Sort returns (worst to best)
        sorted_returns = sorted(returns)

        # Find percentile index
        percentile_rank = 1 - float(confidence_level)  # e.g., 0.05 for 95% confidence
        var_index = int(len(sorted_returns) * percentile_rank)

        # Ensure index is valid
        var_index = max(0, min(var_index, len(sorted_returns) - 1))

        # Get VaR return (this is a loss, so negative)
        var_return = sorted_returns[var_index]

        # VaR = -return × portfolio_value
        # (negative return means loss, so VaR is positive)
        var_amount = -var_return * portfolio_value

        # Ensure VaR is positive (represents potential loss)
        var_amount = abs(var_amount)

        logger.debug(
            "var_calculated",
            confidence_level=f"{float(confidence_level):.1%}",
            var_amount=f"${float(var_amount):,.2f}",
            var_return=f"{float(var_return):.2%}",
            num_returns=len(returns),
        )

        return var_amount

    def _get_portfolio_returns(self, portfolio: Any) -> list[Decimal]:
        """Get portfolio-level returns (weighted by allocation)."""
        if not portfolio.strategies:
            return []

        # Get minimum return length
        min_length = (
            min(
                len(alloc.performance.returns)
                for alloc in portfolio.strategies.values()
                if len(alloc.performance.returns) > 0
            )
            if any(len(alloc.performance.returns) > 0 for alloc in portfolio.strategies.values())
            else 0
        )

        if min_length == 0:
            return []

        # Calculate weighted portfolio returns
        portfolio_returns = []
        for i in range(min(min_length, self.lookback_window)):
            period_return = Decimal("0")
            total_weight = Decimal("0")

            for alloc in portfolio.strategies.values():
                if i < len(alloc.performance.returns):
                    weight = alloc.allocated_capital / portfolio.total_capital
                    period_return += alloc.performance.returns[i] * weight
                    total_weight += weight

            if total_weight > Decimal("0"):
                portfolio_returns.append(period_return)

        return portfolio_returns

    def calculate_correlation_matrix(self, portfolio: Any) -> pd.DataFrame | None:
        """Calculate correlation matrix between strategies using Polars.

        Pearson Correlation Formula:
        ============================
            ρ(X,Y) = Cov(X,Y) / (σ_X × σ_Y)

        Where:
            Cov(X,Y) = E[(X - μ_X)(Y - μ_Y)]
            σ_X = std(X)
            σ_Y = std(Y)

        Properties:
            - ρ ∈ [-1, 1]
            - ρ = 1: perfect positive correlation
            - ρ = 0: no correlation
            - ρ = -1: perfect negative correlation

        Args:
            portfolio: PortfolioAllocator instance

        Returns:
            DataFrame with correlation matrix or None if insufficient data
        """
        # Need at least 2 strategies
        if len(portfolio.strategies) < 2:
            return None

        # Collect strategy returns
        strategy_returns = {}
        for strategy_id, alloc in portfolio.strategies.items():
            if len(alloc.performance.returns) > 0:
                strategy_returns[strategy_id] = alloc.performance.returns

        if len(strategy_returns) < 2:
            return None

        # Find minimum length
        min_length = min(len(returns) for returns in strategy_returns.values())

        if min_length < 2:
            return None

        # Create Polars DataFrame with aligned returns
        returns_data = {
            strategy_id: [float(r) for r in returns[-min_length:]]
            for strategy_id, returns in strategy_returns.items()
        }

        # Use Polars for efficient correlation calculation
        df_pl = pl.DataFrame(returns_data)

        # Calculate correlation matrix using Polars
        # Convert to pandas for compatibility
        corr_matrix = df_pl.to_pandas().corr()

        logger.debug(
            "correlation_matrix_calculated",
            num_strategies=len(corr_matrix),
            min_correlation=f"{float(corr_matrix.min().min()):.2f}",
            max_correlation=f"{float(corr_matrix.max().max()):.2f}",
        )

        return corr_matrix

    def _calculate_strategy_correlations(
        self, portfolio: Any
    ) -> tuple[Decimal | None, Decimal | None]:
        """Calculate average and max strategy correlation."""
        corr_matrix = self.calculate_correlation_matrix(portfolio)

        if corr_matrix is None:
            return None, None

        # Get off-diagonal correlations (exclude diagonal which is 1.0)
        correlations = []
        strategies = list(corr_matrix.columns)

        for i in range(len(strategies)):
            for j in range(i + 1, len(strategies)):
                corr = corr_matrix.iloc[i, j]
                correlations.append(Decimal(str(corr)))

        if not correlations:
            return None, None

        avg_corr = sum(correlations) / Decimal(str(len(correlations)))
        max_corr = max(correlations)

        return avg_corr, max_corr

    def _calculate_portfolio_beta(self, portfolio: Any, market_returns: list[Decimal]) -> Decimal:
        """Calculate portfolio beta against market index.

        Beta Formula:
        =============
            β = Cov(R_portfolio, R_market) / Var(R_market)

        Where:
            Cov(R_p, R_m) = E[(R_p - μ_p)(R_m - μ_m)]
            Var(R_m) = E[(R_m - μ_m)²]

        Interpretation:
            β = 1.0: Portfolio moves with market
            β > 1.0: Portfolio more volatile than market
            β < 1.0: Portfolio less volatile than market
            β = 0.0: No correlation with market

        Args:
            portfolio: PortfolioAllocator instance
            market_returns: Market index returns

        Returns:
            Portfolio beta
        """
        # Get portfolio returns
        portfolio_returns = self._get_portfolio_returns(portfolio)

        if len(portfolio_returns) < 2 or len(market_returns) < 2:
            return Decimal("0")

        # Align lengths
        min_length = min(len(portfolio_returns), len(market_returns))
        portfolio_returns = portfolio_returns[-min_length:]
        market_returns = market_returns[-min_length:]

        # Convert to numpy
        portfolio_array = np.array([float(r) for r in portfolio_returns])
        market_array = np.array([float(r) for r in market_returns])

        # Calculate covariance and variance
        covariance = np.cov(portfolio_array, market_array)[0, 1]
        market_variance = np.var(market_array, ddof=1)

        if market_variance == 0:
            return Decimal("0")

        # Calculate beta
        beta = Decimal(str(covariance / market_variance))

        logger.debug(
            "portfolio_beta_calculated",
            beta=f"{float(beta):.2f}",
            covariance=f"{covariance:.6f}",
            market_variance=f"{market_variance:.6f}",
        )

        return beta

    def apply_volatility_targeting(
        self, portfolio: Any, current_allocations: dict[str, Decimal]
    ) -> dict[str, Decimal]:
        """Apply volatility targeting to adjust allocations.

        Volatility Targeting Algorithm:
        ===============================
        1. Calculate current portfolio volatility
        2. Calculate scaling factor: target_vol / current_vol
        3. Scale all allocations by factor
        4. Normalize to sum to 1.0

        Formula:
            new_allocation_i = current_allocation_i × (target_vol / current_vol)

        Args:
            portfolio: PortfolioAllocator instance
            current_allocations: Current allocation percentages

        Returns:
            Adjusted allocations maintaining target volatility
        """
        if self.limits.target_volatility is None:
            return current_allocations

        # Calculate current portfolio volatility
        current_vol = self._calculate_portfolio_volatility(portfolio)

        if current_vol == Decimal("0"):
            logger.warning("volatility_targeting_zero_volatility")
            return current_allocations

        # Calculate scaling factor
        target_vol = self.limits.target_volatility
        scaling_factor = target_vol / current_vol

        # Scale allocations
        scaled_allocations = {
            strategy_id: allocation * scaling_factor
            for strategy_id, allocation in current_allocations.items()
        }

        # Normalize to sum to 1.0
        total = sum(scaled_allocations.values())
        if total > Decimal("0"):
            normalized = {
                strategy_id: allocation / total
                for strategy_id, allocation in scaled_allocations.items()
            }
        else:
            normalized = current_allocations

        logger.info(
            "volatility_targeting_applied",
            current_vol=f"{float(current_vol):.1%}",
            target_vol=f"{float(target_vol):.1%}",
            scaling_factor=f"{float(scaling_factor):.3f}",
            adjustments={
                sid: f"{float(current_allocations[sid]):.1%} → {float(normalized[sid]):.1%}"
                for sid in current_allocations
            },
        )

        return normalized


def create_hedge_fund_risk_config() -> RiskLimits:
    """Example: Create typical hedge fund risk limits.

    Hedge Fund Style:
    ================
    - Conservative fund (long-only equity)
    - Max leverage: 1.5x
    - Max single stock: 10%
    - Max drawdown: 12%
    - Target volatility: 10% annualized

    Returns:
        RiskLimits configuration
    """
    limits = RiskLimits(
        # Leverage limits (conservative)
        max_portfolio_leverage=Decimal("1.5"),  # 1.5x max
        warn_portfolio_leverage=Decimal("1.3"),  # 1.3x warning
        # Concentration limits (diversified)
        max_single_asset_exposure=Decimal("0.10"),  # 10% max per stock
        warn_single_asset_exposure=Decimal("0.08"),  # 8% warning
        # Drawdown limits (tight risk control)
        max_drawdown=Decimal("0.12"),  # 12% max drawdown
        warn_drawdown=Decimal("0.08"),  # 8% warning
        halt_drawdown=Decimal("0.15"),  # 15% halt trading
        # Volatility targeting
        target_volatility=Decimal("0.10"),  # 10% target vol
        max_volatility=Decimal("0.15"),  # 15% max vol
        # VaR limits
        max_var_pct=Decimal("0.03"),  # 3% max daily VaR
        var_confidence_level=Decimal("0.95"),  # 95% confidence
        # Correlation limits
        max_strategy_correlation=Decimal("0.70"),  # 0.7 max correlation
    )

    logger.info(
        "hedge_fund_risk_config_created",
        style="Conservative Long-Only Equity",
        max_leverage="1.5x",
        max_concentration="10%",
        max_drawdown="12%",
        target_volatility="10%",
    )

    return limits
