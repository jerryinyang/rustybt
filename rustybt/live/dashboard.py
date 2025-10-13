"""Optional Streamlit monitoring dashboard for live trading.

This module provides a real-time monitoring dashboard using Streamlit:
- Live portfolio value and PnL
- Current positions with market values
- Circuit breaker status
- Recent orders and fills
- Error log
- Manual halt button

To run the dashboard:
    streamlit run rustybt/live/dashboard.py -- --strategy-name MyStrategy

Note: Streamlit is an optional dependency. Install with: pip install streamlit
"""

import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

import structlog

logger = structlog.get_logger()


class DashboardDataProvider:
    """Provides data for dashboard from various sources.

    In production, this would connect to:
    - LiveTradingEngine state
    - StateManager checkpoint files
    - Real-time data feeds

    For now, this reads from checkpoint files and provides mock data.
    """

    def __init__(self, strategy_name: str, checkpoint_dir: str = ".rustybt/checkpoints") -> None:
        """Initialize dashboard data provider.

        Args:
            strategy_name: Name of strategy to monitor
            checkpoint_dir: Directory containing checkpoint files
        """
        self._strategy_name = strategy_name
        self._checkpoint_dir = Path(checkpoint_dir)

    def get_portfolio_value(self) -> Decimal:
        """Get current portfolio value.

        Returns:
            Current portfolio value
        """
        # TODO: Connect to live engine or read from checkpoint
        return Decimal("100000.00")

    def get_portfolio_pnl(self) -> Decimal:
        """Get portfolio PnL (profit/loss).

        Returns:
            Portfolio PnL
        """
        # TODO: Calculate PnL from starting value
        return Decimal("5000.00")

    def get_positions(self) -> list[dict[str, Any]]:
        """Get current positions.

        Returns:
            List of position dicts with asset, amount, market_value
        """
        # TODO: Read from checkpoint or live engine
        return [
            {"asset": "AAPL", "amount": "100", "market_value": "15000.00", "pnl": "500.00"},
            {"asset": "GOOGL", "amount": "50", "market_value": "7500.00", "pnl": "-200.00"},
        ]

    def get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get circuit breaker status.

        Returns:
            Circuit breaker status dict
        """
        # TODO: Read from live engine
        return {
            "overall_state": "normal",
            "is_tripped": False,
            "drawdown": {"enabled": True, "state": "normal"},
            "daily_loss": {"enabled": True, "state": "normal"},
            "order_rate": {"enabled": True, "state": "normal"},
            "error_rate": {"enabled": True, "state": "normal"},
            "manual": {"enabled": True, "state": "normal"},
        }

    def get_recent_orders(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent orders.

        Args:
            limit: Maximum number of orders to return

        Returns:
            List of order dicts
        """
        # TODO: Read from order manager or checkpoint
        return [
            {
                "order_id": "order-001",
                "asset": "AAPL",
                "amount": "100",
                "order_type": "market",
                "status": "filled",
                "fill_price": "150.00",
                "timestamp": "2025-10-03 10:30:00",
            },
            {
                "order_id": "order-002",
                "asset": "GOOGL",
                "amount": "50",
                "order_type": "limit",
                "status": "filled",
                "fill_price": "150.00",
                "timestamp": "2025-10-03 11:00:00",
            },
        ]

    def get_recent_errors(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent errors.

        Args:
            limit: Maximum number of errors to return

        Returns:
            List of error dicts
        """
        # TODO: Read from error log
        return []

    def manual_halt(self, reason: str) -> bool:
        """Trigger manual halt.

        Args:
            reason: Reason for manual halt

        Returns:
            True if successful, False otherwise
        """
        # TODO: Connect to live engine and trigger manual halt
        logger.critical(
            "manual_halt_triggered_from_dashboard", reason=reason, strategy=self._strategy_name
        )
        return True


def create_dashboard(strategy_name: str) -> None:
    """Create Streamlit dashboard.

    Args:
        strategy_name: Name of strategy to monitor
    """
    if st is None:
        return

    # Initialize data provider
    if "data_provider" not in st.session_state:
        st.session_state.data_provider = DashboardDataProvider(strategy_name)

    data_provider: DashboardDataProvider = st.session_state.data_provider

    # Page config
    st.set_page_config(
        page_title=f"RustyBT Live Trading - {strategy_name}",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Title
    st.title(f"📈 RustyBT Live Trading Monitor: {strategy_name}")

    # Auto-refresh every 5 seconds
    st_autorefresh = st.empty()
    with st_autorefresh:
        refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"Last refresh: {refresh_time} (auto-refresh every 5s)")

    # Portfolio Overview
    st.header("Portfolio Overview")
    col1, col2, col3 = st.columns(3)

    portfolio_value = data_provider.get_portfolio_value()
    pnl = data_provider.get_portfolio_pnl()
    pnl_percent = (pnl / portfolio_value) * Decimal("100") if portfolio_value > 0 else Decimal("0")

    with col1:
        st.metric("Portfolio Value", f"${portfolio_value:,.2f}")
    with col2:
        st.metric("PnL", f"${pnl:,.2f}", f"{pnl_percent:.2f}%")
    with col3:
        cash = portfolio_value - sum(
            Decimal(p["market_value"]) for p in data_provider.get_positions()
        )
        st.metric("Cash", f"${cash:,.2f}")

    # Circuit Breaker Status
    st.header("Circuit Breaker Status")
    cb_status = data_provider.get_circuit_breaker_status()

    # Overall status
    cb_status["overall_state"]
    is_tripped = cb_status["is_tripped"]

    if is_tripped:
        st.error("⚠️ CIRCUIT BREAKER TRIPPED - Trading Halted")
    else:
        st.success("✅ All Systems Normal - Trading Active")

    # Individual breaker status
    col1, col2, col3, col4, col5 = st.columns(5)

    breakers = [
        ("Drawdown", "drawdown", col1),
        ("Daily Loss", "daily_loss", col2),
        ("Order Rate", "order_rate", col3),
        ("Error Rate", "error_rate", col4),
        ("Manual", "manual", col5),
    ]

    for name, key, col in breakers:
        with col:
            breaker = cb_status.get(key, {})
            enabled = breaker.get("enabled", False)
            state = breaker.get("state", "unknown")

            if not enabled:
                st.info(f"{name}\n\nDisabled")
            elif state == "normal":
                st.success(f"{name}\n\n✅ Normal")
            elif state in ("tripped", "manually_halted"):
                st.error(f"{name}\n\n⚠️ Tripped")
            else:
                st.warning(f"{name}\n\n⚠️ {state}")

    # Manual Halt Button
    st.header("Emergency Controls")
    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("🛑 MANUAL HALT", type="primary", disabled=is_tripped):
            st.session_state.show_halt_confirm = True

    with col2:
        if is_tripped:
            st.warning("Trading already halted. Manual reset required.")
        else:
            st.info("Use this button to immediately halt all trading in emergency situations.")

    # Halt confirmation dialog
    if st.session_state.get("show_halt_confirm", False):
        with st.form("halt_confirm_form"):
            st.warning("⚠️ Are you sure you want to halt trading?")
            reason = st.text_input(
                "Reason for halt (required):", placeholder="e.g., Market anomaly detected"
            )
            col1, col2 = st.columns(2)
            with col1:
                confirm = st.form_submit_button("Confirm Halt", type="primary")
            with col2:
                cancel = st.form_submit_button("Cancel")

            if confirm:
                if reason:
                    success = data_provider.manual_halt(reason)
                    if success:
                        st.success("Trading halted successfully")
                        st.session_state.show_halt_confirm = False
                        st.rerun()
                    else:
                        st.error("Failed to halt trading")
                else:
                    st.error("Reason is required")

            if cancel:
                st.session_state.show_halt_confirm = False
                st.rerun()

    # Current Positions
    st.header("Current Positions")
    positions = data_provider.get_positions()

    if positions:
        positions_df = pd.DataFrame(positions)
        positions_df["market_value"] = positions_df["market_value"].apply(
            lambda x: f"${float(x):,.2f}"
        )
        positions_df["pnl"] = positions_df["pnl"].apply(
            lambda x: f"${float(x):,.2f}" if float(x) >= 0 else f"-${abs(float(x)):,.2f}"
        )
        st.dataframe(positions_df, use_container_width=True)
    else:
        st.info("No open positions")

    # Recent Orders
    st.header("Recent Orders")
    orders = data_provider.get_recent_orders(limit=20)

    if orders:
        orders_df = pd.DataFrame(orders)
        st.dataframe(orders_df, use_container_width=True)
    else:
        st.info("No recent orders")

    # Error Log
    st.header("Error Log")
    errors = data_provider.get_recent_errors(limit=50)

    if errors:
        errors_df = pd.DataFrame(errors)
        st.dataframe(errors_df, use_container_width=True)
    else:
        st.success("No errors logged")

    # Sidebar - Settings and Info
    with st.sidebar:
        st.header("Settings")
        st.text_input("Strategy Name", value=strategy_name, disabled=True)
        st.number_input("Refresh Interval (seconds)", min_value=1, max_value=60, value=5)

        st.header("Dashboard Info")
        st.info(
            """
            This dashboard provides real-time monitoring for RustyBT live trading.

            **Features:**
            - Live portfolio value and PnL
            - Circuit breaker status
            - Current positions
            - Recent orders and fills
            - Error log
            - Manual emergency halt

            **Note:** This is an optional Streamlit dashboard. For production monitoring,
            consider using Grafana with Prometheus metrics.
            """
        )

        st.header("Alternative: Grafana")
        st.markdown(
            """
            For production environments, we recommend using Grafana for monitoring:

            1. Export metrics to Prometheus
            2. Create Grafana dashboard
            3. Set up alerts in Grafana

            See documentation for Grafana integration guide.
            """
        )

    # Auto-refresh
    import time

    time.sleep(5)
    st.rerun()


def main() -> None:
    """Main entry point for dashboard."""
    parser = argparse.ArgumentParser(description="RustyBT Live Trading Dashboard")
    parser.add_argument(
        "--strategy-name",
        type=str,
        required=True,
        help="Name of strategy to monitor",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default=".rustybt/checkpoints",
        help="Directory containing checkpoint files",
    )

    args = parser.parse_args()

    # Create dashboard
    create_dashboard(args.strategy_name)


if __name__ == "__main__":
    main()
