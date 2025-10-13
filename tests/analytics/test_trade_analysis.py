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
Tests for trade analysis and diagnostics.

Test coverage:
- Unit tests: Trade extraction from transactions
- Unit tests: Entry/exit quality calculation
- Unit tests: MAE/MFE calculation
- Unit tests: All analysis methods
- Property tests: Sum of trade PnLs equals total portfolio return
- Integration tests: Full trade analysis on synthetic backtest
- Edge case handling: No trades, single trade, insufficient data
"""

from datetime import datetime, timedelta
from decimal import Decimal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.analytics.trade_analysis import (
    InsufficientTradeDataError,
    TradeAnalyzer,
)
from rustybt.assets import Equity, ExchangeInfo
from rustybt.finance.decimal.transaction import DecimalTransaction

# ============================================================================
# Fixtures and Test Helpers
# ============================================================================

# Exchange info for tests
NASDAQ = ExchangeInfo("NASDAQ", "NASDAQ", "US")
NYSE = ExchangeInfo("NYSE", "NYSE", "US")


class MockBacktestResult:
    """Mock backtest result for testing."""

    def __init__(self, transactions: list, price_data: pd.DataFrame):
        self.transactions = transactions
        self.price_data = price_data
        self.portfolio_history = None


def create_test_asset(symbol: str = "AAPL", exchange_info: ExchangeInfo = NASDAQ) -> Equity:
    """Create a test equity asset."""
    return Equity(
        sid=hash(symbol) % 10000,
        exchange_info=exchange_info,
        symbol=symbol,
        asset_name=f"{symbol} Test Asset",
    )


@pytest.fixture
def sample_asset():
    """Create sample asset for testing."""
    return create_test_asset("AAPL")


@pytest.fixture
def sample_transactions(sample_asset):
    """Create sample transaction stream with multiple round-trip trades."""
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    transactions = [
        # Trade 1: Buy 100 @ $150, Sell 100 @ $155 (Winner)
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=sample_asset,
            amount=Decimal("100"),
            price=Decimal("150.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=4),
            order_id="order_2",
            asset=sample_asset,
            amount=Decimal("-100"),
            price=Decimal("155.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        # Trade 2: Buy 50 @ $156, Sell 50 @ $152 (Loser)
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=5),
            order_id="order_3",
            asset=sample_asset,
            amount=Decimal("50"),
            price=Decimal("156.00"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.25"),
        ),
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=8),
            order_id="order_4",
            asset=sample_asset,
            amount=Decimal("-50"),
            price=Decimal("152.00"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.25"),
        ),
        # Trade 3: Buy 200 @ $153, Sell 200 @ $158 (Big Winner)
        DecimalTransaction(
            timestamp=base_time + timedelta(days=1),
            order_id="order_5",
            asset=sample_asset,
            amount=Decimal("200"),
            price=Decimal("153.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("1.00"),
        ),
        DecimalTransaction(
            timestamp=base_time + timedelta(days=2),
            order_id="order_6",
            asset=sample_asset,
            amount=Decimal("-200"),
            price=Decimal("158.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("1.00"),
        ),
    ]

    return transactions


@pytest.fixture
def sample_price_data(sample_asset):
    """Create sample price data for MAE/MFE calculation."""
    base_time = datetime(2023, 1, 1, 10, 0, 0)
    times = [base_time + timedelta(hours=i) for i in range(72)]  # 3 days of hourly data

    # Generate price series with some volatility
    np.random.seed(42)
    base_price = 150.0
    prices = [base_price + np.random.uniform(-5, 5) for _ in times]

    df = pd.DataFrame({sample_asset.symbol: prices}, index=times)

    return df


@pytest.fixture
def sample_backtest_result(sample_transactions, sample_price_data):
    """Create sample backtest result."""
    return MockBacktestResult(transactions=sample_transactions, price_data=sample_price_data)


@pytest.fixture
def analyzer(sample_backtest_result):
    """Create TradeAnalyzer with sample data."""
    return TradeAnalyzer(sample_backtest_result)


# ============================================================================
# Unit Tests: Initialization and Validation
# ============================================================================


def test_initialization_with_valid_data(sample_backtest_result):
    """Test initialization with valid backtest result."""
    analyzer = TradeAnalyzer(sample_backtest_result)

    assert analyzer.backtest_result is not None
    assert len(analyzer.transactions) > 0
    assert len(analyzer.trades) > 0


def test_initialization_missing_transactions():
    """Test initialization fails when transactions missing."""

    class InvalidResult:
        pass

    result = InvalidResult()

    with pytest.raises(ValueError, match="transactions"):
        TradeAnalyzer(result)


def test_initialization_missing_price_data(sample_transactions):
    """Test initialization fails when price_data missing."""

    class InvalidResult:
        def __init__(self):
            self.transactions = sample_transactions

    result = InvalidResult()

    with pytest.raises(ValueError, match="price_data"):
        TradeAnalyzer(result)


def test_initialization_no_trades():
    """Test initialization fails when no completed trades found."""
    # Create backtest with only open positions (no exits)
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    transactions = [
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("150.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
    ]

    price_data = pd.DataFrame({asset.symbol: [150.0]}, index=[base_time])

    result = MockBacktestResult(transactions=transactions, price_data=price_data)

    with pytest.raises(InsufficientTradeDataError, match="No completed trades"):
        TradeAnalyzer(result)


# ============================================================================
# Unit Tests: Trade Extraction
# ============================================================================


def test_trade_extraction_basic(analyzer):
    """Test basic trade extraction from transactions."""
    assert len(analyzer.trades) == 3

    # Verify first trade
    trade1 = analyzer.trades[0]
    assert trade1.amount == Decimal("100")
    assert trade1.entry_price == Decimal("150.00")
    assert trade1.exit_price == Decimal("155.00")
    assert trade1.pnl > Decimal("0")  # Should be profitable


def test_trade_extraction_long_trade(analyzer):
    """Test long trade extraction and PnL calculation."""
    # First trade is a long
    trade = analyzer.trades[0]

    # Long: PnL = (exit - entry) * amount - costs
    expected_gross = (Decimal("155.00") - Decimal("150.00")) * Decimal("100")
    expected_costs = Decimal("1.00") + Decimal("0.50") + Decimal("1.00") + Decimal("0.50")
    expected_pnl = expected_gross - expected_costs

    assert abs(trade.pnl - expected_pnl) < Decimal("0.01")


def test_trade_extraction_short_trade():
    """Test short trade extraction and PnL calculation."""
    asset = create_test_asset("SPY")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    transactions = [
        # Short 100 @ $200, Cover @ $195 (profit)
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=asset,
            amount=Decimal("-100"),
            price=Decimal("200.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=2),
            order_id="order_2",
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("195.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
    ]

    price_data = pd.DataFrame(
        {asset.symbol: [200.0, 198.0, 195.0]},
        index=[base_time + timedelta(hours=i) for i in range(3)],
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    assert len(analyzer.trades) == 1
    trade = analyzer.trades[0]

    # Short: PnL = (entry - exit) * amount - costs
    expected_gross = (Decimal("200.00") - Decimal("195.00")) * Decimal("100")
    expected_costs = Decimal("1.00") + Decimal("0.50") + Decimal("1.00") + Decimal("0.50")
    expected_pnl = expected_gross - expected_costs

    assert abs(trade.pnl - expected_pnl) < Decimal("0.01")


def test_trade_extraction_partial_close():
    """Test partial position close creates multiple trades."""
    asset = create_test_asset("MSFT")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    transactions = [
        # Buy 100
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("300.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        # Sell 50 (partial close)
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=2),
            order_id="order_2",
            asset=asset,
            amount=Decimal("-50"),
            price=Decimal("305.00"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.25"),
        ),
        # Sell remaining 50
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=4),
            order_id="order_3",
            asset=asset,
            amount=Decimal("-50"),
            price=Decimal("310.00"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.25"),
        ),
    ]

    price_data = pd.DataFrame(
        {asset.symbol: [300.0, 305.0, 310.0]},
        index=[base_time + timedelta(hours=i * 2) for i in range(3)],
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    # Should create 2 separate trades
    assert len(analyzer.trades) == 2

    # First trade: 50 shares @ 300 -> 305
    trade1 = analyzer.trades[0]
    assert trade1.exit_price == Decimal("305.00")

    # Second trade: 50 shares @ 300 -> 310
    trade2 = analyzer.trades[1]
    assert trade2.exit_price == Decimal("310.00")


def test_trade_extraction_multiple_assets():
    """Test trade extraction with multiple assets."""
    asset1 = create_test_asset("AAPL")
    asset2 = create_test_asset("GOOGL")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    transactions = [
        # AAPL trade
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=asset1,
            amount=Decimal("100"),
            price=Decimal("150.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        # GOOGL trade (interleaved)
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=1),
            order_id="order_2",
            asset=asset2,
            amount=Decimal("50"),
            price=Decimal("2800.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("1.00"),
        ),
        # Close AAPL
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=2),
            order_id="order_3",
            asset=asset1,
            amount=Decimal("-100"),
            price=Decimal("155.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        # Close GOOGL
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=3),
            order_id="order_4",
            asset=asset2,
            amount=Decimal("-50"),
            price=Decimal("2850.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("1.00"),
        ),
    ]

    price_data = pd.DataFrame(
        {
            asset1.symbol: [150.0, 152.0, 155.0, 156.0],
            asset2.symbol: [2800.0, 2820.0, 2840.0, 2850.0],
        },
        index=[base_time + timedelta(hours=i) for i in range(4)],
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    assert len(analyzer.trades) == 2

    # Verify each asset has one trade
    aapl_trades = [t for t in analyzer.trades if t.asset == asset1]
    googl_trades = [t for t in analyzer.trades if t.asset == asset2]

    assert len(aapl_trades) == 1
    assert len(googl_trades) == 1


# ============================================================================
# Unit Tests: MAE/MFE Calculation
# ============================================================================


def test_mae_calculation_long_trade():
    """Test MAE calculation for long trade."""
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    # Long trade: entry @ 100, worst price during trade = 95
    transactions = [
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("100.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=4),
            order_id="order_2",
            asset=asset,
            amount=Decimal("-100"),
            price=Decimal("105.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
    ]

    # Price drops to 95 during trade (MAE = 5%)
    price_data = pd.DataFrame(
        {asset.symbol: [100.0, 98.0, 95.0, 98.0, 105.0]},
        index=[base_time + timedelta(hours=i) for i in range(5)],
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    trade = analyzer.trades[0]

    # MAE = (100 - 95) / 100 = 5%
    expected_mae = Decimal("0.05")
    assert abs(trade.mae - expected_mae) < Decimal("0.01")


def test_mfe_calculation_long_trade():
    """Test MFE calculation for long trade."""
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    # Long trade: entry @ 100, best price during trade = 110
    transactions = [
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("100.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=4),
            order_id="order_2",
            asset=asset,
            amount=Decimal("-100"),
            price=Decimal("105.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
    ]

    # Price rises to 110 during trade (MFE = 10%)
    price_data = pd.DataFrame(
        {asset.symbol: [100.0, 105.0, 110.0, 108.0, 105.0]},
        index=[base_time + timedelta(hours=i) for i in range(5)],
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    trade = analyzer.trades[0]

    # MFE = (110 - 100) / 100 = 10%
    expected_mfe = Decimal("0.10")
    assert abs(trade.mfe - expected_mfe) < Decimal("0.01")


# ============================================================================
# Unit Tests: Analysis Methods
# ============================================================================


def test_analyze_trades_returns_complete_analysis(analyzer):
    """Test that analyze_trades returns all expected components."""
    analysis = analyzer.analyze_trades()

    assert "trade_log" in analysis
    assert "summary_stats" in analysis
    assert "entry_exit_quality" in analysis
    assert "holding_period_dist" in analysis
    assert "win_loss_dist" in analysis
    assert "mae_mfe_analysis" in analysis
    assert "clustering" in analysis
    assert "slippage_analysis" in analysis
    assert "commission_impact" in analysis


def test_summary_stats_calculation(analyzer):
    """Test summary statistics calculation."""
    analysis = analyzer.analyze_trades()
    stats = analysis["summary_stats"]

    assert stats["total_trades"] == 3
    assert 0 <= stats["win_rate"] <= 1
    assert "average_win" in stats
    assert "average_loss" in stats
    assert "profit_factor" in stats
    assert "total_pnl" in stats


def test_win_rate_calculation():
    """Test win rate calculation with known data."""
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    # Create 3 trades: 2 winners, 1 loser
    transactions = []
    for i in range(3):
        # Entry
        transactions.append(
            DecimalTransaction(
                timestamp=base_time + timedelta(hours=i * 4),
                order_id=f"order_{i * 2}",
                asset=asset,
                amount=Decimal("100"),
                price=Decimal("100.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        )
        # Exit (winner if i < 2, loser if i == 2)
        exit_price = Decimal("105.00") if i < 2 else Decimal("95.00")
        transactions.append(
            DecimalTransaction(
                timestamp=base_time + timedelta(hours=i * 4 + 2),
                order_id=f"order_{i * 2 + 1}",
                asset=asset,
                amount=Decimal("-100"),
                price=exit_price,
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        )

    price_data = pd.DataFrame(
        {asset.symbol: [100.0] * 20}, index=[base_time + timedelta(hours=i) for i in range(20)]
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    analysis = analyzer.analyze_trades()
    stats = analysis["summary_stats"]

    # Win rate should be 2/3
    expected_win_rate = 2.0 / 3.0
    assert abs(stats["win_rate"] - expected_win_rate) < 0.01


def test_holding_period_analysis(analyzer):
    """Test holding period distribution analysis."""
    analysis = analyzer.analyze_trades()
    holding = analysis["holding_period_dist"]

    assert "mean_holding_hours" in holding
    assert "median_holding_hours" in holding
    assert "min_holding_hours" in holding
    assert "max_holding_hours" in holding
    assert holding["mean_holding_hours"] > 0


def test_mae_mfe_analysis(analyzer):
    """Test MAE/MFE analysis."""
    analysis = analyzer.analyze_trades()
    mae_mfe = analysis["mae_mfe_analysis"]

    assert "average_mae" in mae_mfe
    assert "average_mfe" in mae_mfe
    assert "max_mae" in mae_mfe
    assert "max_mfe" in mae_mfe
    assert mae_mfe["average_mae"] >= 0
    assert mae_mfe["average_mfe"] >= 0


def test_clustering_analysis(analyzer):
    """Test trade clustering analysis."""
    analysis = analyzer.analyze_trades()
    clustering = analysis["clustering"]

    assert "unique_assets_traded" in clustering
    assert "top_3_asset_concentration" in clustering
    assert "avg_trades_per_day" in clustering
    assert clustering["unique_assets_traded"] > 0


def test_slippage_analysis(analyzer):
    """Test slippage analysis."""
    analysis = analyzer.analyze_trades()
    slippage = analysis["slippage_analysis"]

    assert "total_slippage" in slippage
    assert "average_slippage_per_trade" in slippage
    assert "excessive_slippage_trades" in slippage
    assert slippage["total_slippage"] >= 0


def test_commission_analysis(analyzer):
    """Test commission impact analysis."""
    analysis = analyzer.analyze_trades()
    commission = analysis["commission_impact"]

    assert "total_commissions" in commission
    assert "average_commission_per_trade" in commission
    assert "high_commission_trades" in commission
    assert commission["total_commissions"] >= 0


def test_analyze_trades_insufficient_data():
    """Test analyze_trades fails with insufficient trades."""
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    # Only one trade
    transactions = [
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("100.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=2),
            order_id="order_2",
            asset=asset,
            amount=Decimal("-100"),
            price=Decimal("105.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
    ]

    price_data = pd.DataFrame(
        {asset.symbol: [100.0, 105.0]}, index=[base_time, base_time + timedelta(hours=2)]
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    with pytest.raises(InsufficientTradeDataError, match="at least 2 trades"):
        analyzer.analyze_trades()


# ============================================================================
# Property Tests
# ============================================================================


@given(
    num_trades=st.integers(min_value=2, max_value=20),
    price_range=st.floats(min_value=50.0, max_value=200.0),
)
@settings(deadline=None, max_examples=50)
def test_property_trade_pnl_sum(num_trades, price_range):
    """Property test: Sum of trade PnLs should equal net portfolio change."""
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    np.random.seed(42)
    transactions = []

    for i in range(num_trades):
        entry_price = Decimal(str(round(price_range + np.random.uniform(-10, 10), 2)))
        exit_price = Decimal(str(round(float(entry_price) + np.random.uniform(-5, 5), 2)))

        if exit_price <= Decimal("0"):
            exit_price = Decimal("1.00")

        transactions.extend(
            [
                DecimalTransaction(
                    timestamp=base_time + timedelta(hours=i * 4),
                    order_id=f"order_{i * 2}",
                    asset=asset,
                    amount=Decimal("100"),
                    price=entry_price,
                    commission=Decimal("1.00"),
                    slippage=Decimal("0.50"),
                ),
                DecimalTransaction(
                    timestamp=base_time + timedelta(hours=i * 4 + 2),
                    order_id=f"order_{i * 2 + 1}",
                    asset=asset,
                    amount=Decimal("-100"),
                    price=exit_price,
                    commission=Decimal("1.00"),
                    slippage=Decimal("0.50"),
                ),
            ]
        )

    price_data = pd.DataFrame(
        {asset.symbol: [float(price_range)] * (num_trades * 4)},
        index=[base_time + timedelta(hours=i) for i in range(num_trades * 4)],
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    # Sum of trade PnLs should equal total PnL
    total_trade_pnl = sum(float(t.pnl) for t in analyzer.trades)

    analysis = analyzer.analyze_trades()
    reported_total_pnl = analysis["summary_stats"]["total_pnl"]

    # Should be equal within floating point precision
    assert abs(total_trade_pnl - reported_total_pnl) < 0.01


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_trade_analysis_integration(analyzer):
    """Integration test: Full trade analysis pipeline."""
    # Run complete analysis
    analysis = analyzer.analyze_trades()

    # Verify all components present and valid
    assert len(analysis["trade_log"]) > 0
    assert analysis["summary_stats"]["total_trades"] > 0
    assert 0 <= analysis["summary_stats"]["win_rate"] <= 1

    # Verify trade log structure
    trade_log = analysis["trade_log"]
    required_columns = [
        "entry_time",
        "exit_time",
        "asset",
        "entry_price",
        "exit_price",
        "pnl",
        "mae",
        "mfe",
    ]
    for col in required_columns:
        assert col in trade_log.columns


def test_visualization_methods_run_without_error(analyzer):
    """Test that all visualization methods run without error."""
    # Note: We don't validate visual output, just that methods execute

    fig1 = analyzer.plot_holding_period_histogram()
    assert isinstance(fig1, plt.Figure)
    plt.close(fig1)

    fig2 = analyzer.plot_win_loss_histogram()
    assert isinstance(fig2, plt.Figure)
    plt.close(fig2)

    fig3 = analyzer.plot_mae_vs_pnl()
    assert isinstance(fig3, plt.Figure)
    plt.close(fig3)

    fig4 = analyzer.plot_mfe_vs_pnl()
    assert isinstance(fig4, plt.Figure)
    plt.close(fig4)

    fig5 = analyzer.plot_trade_timeline()
    assert isinstance(fig5, plt.Figure)
    plt.close(fig5)

    fig6 = analyzer.plot_trade_heatmap()
    assert isinstance(fig6, plt.Figure)
    plt.close(fig6)


# ============================================================================
# Edge Cases
# ============================================================================


def test_all_winning_trades():
    """Test analysis with all winning trades."""
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    transactions = []
    for i in range(5):
        transactions.extend(
            [
                DecimalTransaction(
                    timestamp=base_time + timedelta(hours=i * 4),
                    order_id=f"order_{i * 2}",
                    asset=asset,
                    amount=Decimal("100"),
                    price=Decimal("100.00"),
                    commission=Decimal("1.00"),
                    slippage=Decimal("0.50"),
                ),
                DecimalTransaction(
                    timestamp=base_time + timedelta(hours=i * 4 + 2),
                    order_id=f"order_{i * 2 + 1}",
                    asset=asset,
                    amount=Decimal("-100"),
                    price=Decimal("110.00"),  # All winners
                    commission=Decimal("1.00"),
                    slippage=Decimal("0.50"),
                ),
            ]
        )

    price_data = pd.DataFrame(
        {asset.symbol: [100.0] * 30}, index=[base_time + timedelta(hours=i) for i in range(30)]
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    analysis = analyzer.analyze_trades()
    stats = analysis["summary_stats"]

    assert stats["win_rate"] == 1.0
    assert stats["loss_count"] == 0
    assert stats["profit_factor"] is None  # Infinite profit factor


def test_all_losing_trades():
    """Test analysis with all losing trades."""
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    transactions = []
    for i in range(5):
        transactions.extend(
            [
                DecimalTransaction(
                    timestamp=base_time + timedelta(hours=i * 4),
                    order_id=f"order_{i * 2}",
                    asset=asset,
                    amount=Decimal("100"),
                    price=Decimal("100.00"),
                    commission=Decimal("1.00"),
                    slippage=Decimal("0.50"),
                ),
                DecimalTransaction(
                    timestamp=base_time + timedelta(hours=i * 4 + 2),
                    order_id=f"order_{i * 2 + 1}",
                    asset=asset,
                    amount=Decimal("-100"),
                    price=Decimal("90.00"),  # All losers
                    commission=Decimal("1.00"),
                    slippage=Decimal("0.50"),
                ),
            ]
        )

    price_data = pd.DataFrame(
        {asset.symbol: [100.0] * 30}, index=[base_time + timedelta(hours=i) for i in range(30)]
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    analysis = analyzer.analyze_trades()
    stats = analysis["summary_stats"]

    assert stats["win_rate"] == 0.0
    assert stats["win_count"] == 0
    assert stats["profit_factor"] == 0.0


def test_zero_commission_and_slippage():
    """Test analysis with zero commissions and slippage."""
    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    transactions = [
        DecimalTransaction(
            timestamp=base_time,
            order_id="order_1",
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("100.00"),
            commission=Decimal("0"),
            slippage=Decimal("0"),
        ),
        DecimalTransaction(
            timestamp=base_time + timedelta(hours=2),
            order_id="order_2",
            asset=asset,
            amount=Decimal("-100"),
            price=Decimal("105.00"),
            commission=Decimal("0"),
            slippage=Decimal("0"),
        ),
    ]

    price_data = pd.DataFrame(
        {asset.symbol: [100.0, 105.0]}, index=[base_time, base_time + timedelta(hours=2)]
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)
    analyzer = TradeAnalyzer(result)

    trade = analyzer.trades[0]

    # PnL should be exactly (105 - 100) * 100 = 500
    expected_pnl = Decimal("500.00")
    assert trade.pnl == expected_pnl


# ============================================================================
# Performance Tests
# ============================================================================


def test_performance_large_trade_set():
    """Test performance with large number of trades."""
    import time

    asset = create_test_asset("TEST")
    base_time = datetime(2023, 1, 1, 10, 0, 0)

    # Generate 1000 trades
    num_trades = 1000
    transactions = []

    np.random.seed(42)
    for i in range(num_trades):
        entry_price = Decimal(str(round(100.0 + np.random.uniform(-10, 10), 2)))
        exit_price = Decimal(str(round(float(entry_price) + np.random.uniform(-5, 5), 2)))

        if exit_price <= Decimal("0"):
            exit_price = Decimal("1.00")

        transactions.extend(
            [
                DecimalTransaction(
                    timestamp=base_time + timedelta(minutes=i * 10),
                    order_id=f"order_{i * 2}",
                    asset=asset,
                    amount=Decimal("100"),
                    price=entry_price,
                    commission=Decimal("1.00"),
                    slippage=Decimal("0.50"),
                ),
                DecimalTransaction(
                    timestamp=base_time + timedelta(minutes=i * 10 + 5),
                    order_id=f"order_{i * 2 + 1}",
                    asset=asset,
                    amount=Decimal("-100"),
                    price=exit_price,
                    commission=Decimal("1.00"),
                    slippage=Decimal("0.50"),
                ),
            ]
        )

    price_data = pd.DataFrame(
        {asset.symbol: [100.0] * (num_trades * 2)},
        index=[base_time + timedelta(minutes=i * 5) for i in range(num_trades * 2)],
    )

    result = MockBacktestResult(transactions=transactions, price_data=price_data)

    start = time.time()
    analyzer = TradeAnalyzer(result)
    analysis = analyzer.analyze_trades()
    elapsed = time.time() - start

    # Should complete in reasonable time (< 5 seconds)
    assert elapsed < 5.0
    assert len(analyzer.trades) == num_trades
    assert analysis["summary_stats"]["total_trades"] == num_trades
