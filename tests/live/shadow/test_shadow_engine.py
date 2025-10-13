"""Unit tests for ShadowBacktestEngine."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
import pytz

from rustybt.algorithm import TradingAlgorithm
from rustybt.assets import AssetFinder, Equity, ExchangeInfo
from rustybt.finance.decimal.commission import NoCommission
from rustybt.finance.decimal.slippage import NoSlippage
from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.engine import ShadowBacktestEngine, ShadowBarData, ShadowContext
from rustybt.live.shadow.models import SignalAlignment
from rustybt.utils.factory import create_simulation_parameters


class SimpleBuyStrategy(TradingAlgorithm):
    """Simple test strategy that buys on every bar."""

    def initialize(self, context):
        """Initialize strategy."""
        context.asset = None

    def handle_data(self, context, data):
        """Buy 10 shares every bar."""
        if context.asset and data.can_trade(context.asset):
            self.order(context.asset, 10)


class ConditionalStrategy(TradingAlgorithm):
    """Strategy that only trades when price > threshold."""

    def initialize(self, context):
        """Initialize strategy."""
        context.asset = None
        context.price_threshold = Decimal("100")

    def handle_data(self, context, data):
        """Buy if price above threshold."""
        if context.asset and data.can_trade(context.asset):
            current_price = data.current(context.asset, "price")
            if current_price and current_price > context.price_threshold:
                self.order(context.asset, 50)


class TestShadowBacktestEngine:
    """Test shadow backtest engine functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ShadowTradingConfig(
            enabled=True,
            signal_match_rate_min=Decimal("0.95"),
        )

    @pytest.fixture
    def exchange_info(self):
        """Create test exchange info."""
        return ExchangeInfo(
            name="NASDAQ",
            canonical_name="NASDAQ",
            country_code="US",
        )

    @pytest.fixture
    def test_asset(self, exchange_info):
        """Create test asset."""
        return Equity(sid=1, exchange_info=exchange_info, symbol="AAPL")

    @pytest.fixture
    def sim_params(self):
        """Create simulation parameters for TradingAlgorithm."""
        return create_simulation_parameters()

    @pytest.fixture
    def asset_finder(self):
        """Create minimal asset finder for testing."""
        # Create a mock asset finder - TradingAlgorithm just needs it to exist
        finder = Mock(spec=AssetFinder)
        return finder

    @pytest.fixture
    def simple_strategy(self, sim_params, asset_finder):
        """Create simple test strategy."""
        return SimpleBuyStrategy(sim_params=sim_params, asset_finder=asset_finder)

    @pytest.fixture
    def engine(self, simple_strategy, config):
        """Create test engine instance."""
        return ShadowBacktestEngine(
            strategy=simple_strategy,
            config=config,
            commission_model=NoCommission(),
            slippage_model=NoSlippage(),
            starting_cash=Decimal("100000"),
        )

    def test_initialization(self, engine, config):
        """Test engine initializes correctly."""
        assert engine.config == config
        assert engine._ledger.starting_cash == Decimal("100000")
        assert not engine._running

    @pytest.mark.asyncio
    async def test_process_market_data_disabled(self, simple_strategy, test_asset):
        """Test processing market data when shadow mode disabled."""
        # Create engine with disabled config
        disabled_config = ShadowTradingConfig(enabled=False)
        disabled_engine = ShadowBacktestEngine(
            strategy=simple_strategy,
            config=disabled_config,
            commission_model=NoCommission(),
            slippage_model=NoSlippage(),
            starting_cash=Decimal("100000"),
        )

        market_data = {test_asset: {"price": Decimal("150.00"), "volume": 1000000}}

        await disabled_engine.process_market_data(datetime.utcnow(), market_data)

        # Should not capture any signals
        assert len(disabled_engine.signal_validator._backtest_signals) == 0

    @pytest.mark.asyncio
    async def test_process_market_data_captures_signal(self, test_asset, simple_strategy, config):
        """Test market data processing captures strategy signals."""
        # Set asset on strategy BEFORE creating engine so it gets cloned
        simple_strategy.asset = test_asset

        # Create engine with strategy that has asset set
        engine = ShadowBacktestEngine(
            strategy=simple_strategy,
            config=config,
            commission_model=NoCommission(),
            slippage_model=NoSlippage(),
            starting_cash=Decimal("100000"),
        )

        market_data = {test_asset: {"price": Decimal("150.00"), "volume": 1000000}}

        await engine.process_market_data(datetime.utcnow(), market_data)

        # Should capture the buy signal from SimpleBuyStrategy
        assert len(engine.signal_validator._backtest_signals) == 1
        signal = engine.signal_validator._backtest_signals[0]
        assert signal.asset == test_asset
        assert signal.side == "BUY"
        assert signal.quantity == Decimal("10")
        assert signal.source == "backtest"

    @pytest.mark.asyncio
    async def test_process_market_data_no_signal_when_cannot_trade(
        self, engine, test_asset, simple_strategy
    ):
        """Test no signal generated when asset has no price data."""
        simple_strategy.asset = test_asset

        # Market data without price
        market_data = {test_asset: {"volume": 1000000}}  # Missing 'price'

        await engine.process_market_data(datetime.utcnow(), market_data)

        # Should not capture signal (can_trade returns False)
        assert len(engine.signal_validator._backtest_signals) == 0

    @pytest.mark.asyncio
    async def test_conditional_strategy_signal_logic(
        self, test_asset, config, sim_params, asset_finder
    ):
        """Test conditional strategy logic is executed correctly."""
        strategy = ConditionalStrategy(sim_params=sim_params, asset_finder=asset_finder)
        strategy.asset = test_asset
        strategy.price_threshold = Decimal("100")

        engine = ShadowBacktestEngine(
            strategy=strategy,
            config=config,
            commission_model=NoCommission(),
            slippage_model=NoSlippage(),
            starting_cash=Decimal("100000"),
        )

        # Price below threshold - should not trade
        market_data_low = {test_asset: {"price": Decimal("95.00"), "volume": 1000000}}
        await engine.process_market_data(datetime.utcnow(), market_data_low)
        assert len(engine.signal_validator._backtest_signals) == 0

        # Price above threshold - should trade
        market_data_high = {test_asset: {"price": Decimal("105.00"), "volume": 1000000}}
        await engine.process_market_data(datetime.utcnow(), market_data_high)
        assert len(engine.signal_validator._backtest_signals) == 1
        signal = engine.signal_validator._backtest_signals[0]
        assert signal.quantity == Decimal("50")

    def test_add_live_signal_matching(self, engine, test_asset):
        """Test adding live signal and matching with backtest signal."""
        # Add backtest signal first
        from rustybt.live.shadow.models import SignalRecord

        ts = datetime.utcnow()
        backtest_signal = SignalRecord(
            timestamp=ts,
            asset=test_asset,
            side="BUY",
            quantity=Decimal("100"),
            price=None,
            order_type="market",
            source="backtest",
        )
        engine.signal_validator.add_backtest_signal(backtest_signal)

        # Add matching live signal
        engine.add_live_signal(
            asset=test_asset,
            side="BUY",
            quantity=Decimal("100"),
            price=None,
            order_type="market",
            timestamp=ts,
        )

        # Should match
        assert len(engine.signal_validator._matched_pairs) == 1
        backtest, live, alignment = engine.signal_validator._matched_pairs[0]
        assert alignment == SignalAlignment.EXACT_MATCH

    def test_check_alignment(self, engine, test_asset):
        """Test alignment checking and circuit breaker integration."""
        # Add some matching signals
        ts = datetime.utcnow().replace(tzinfo=pytz.UTC)
        for i in range(98):
            from rustybt.live.shadow.models import SignalRecord

            signal = SignalRecord(
                timestamp=ts,
                asset=test_asset,
                side="BUY",
                quantity=Decimal("100"),
                price=None,
                order_type="market",
                source="backtest",
            )
            engine.signal_validator.add_backtest_signal(signal)
            engine.add_live_signal(
                asset=test_asset,
                side="BUY",
                quantity=Decimal("100"),
                price=None,
                order_type="market",
                timestamp=ts,
            )

        # Check alignment - should pass (98% match rate)
        is_aligned = engine.check_alignment()
        assert is_aligned is True
        assert not engine.circuit_breaker.is_tripped

    def test_get_alignment_metrics(self, engine):
        """Test getting alignment metrics for monitoring."""
        metrics_dict = engine.get_alignment_metrics()

        assert "execution_quality" in metrics_dict
        assert "timestamp" in metrics_dict
        assert "backtest_signal_count" in metrics_dict
        assert "live_signal_count" in metrics_dict
        assert "signal_match_rate" in metrics_dict

    @pytest.mark.asyncio
    async def test_start_stop(self, engine):
        """Test engine start/stop lifecycle."""
        assert not engine._running

        await engine.start()
        assert engine._running

        await engine.stop()
        assert not engine._running

    @pytest.mark.asyncio
    async def test_start_when_disabled(self, engine):
        """Test start does nothing when shadow mode disabled."""
        from dataclasses import replace

        engine.config = replace(engine.config, enabled=False)

        await engine.start()
        assert not engine._running

    def test_reset(self, engine, test_asset):
        """Test reset clears all engine state."""
        # Add some signals
        from rustybt.live.shadow.models import SignalRecord

        signal = SignalRecord(
            timestamp=datetime.utcnow(),
            asset=test_asset,
            side="BUY",
            quantity=Decimal("100"),
            price=None,
            order_type="market",
            source="backtest",
        )
        engine.signal_validator.add_backtest_signal(signal)

        assert len(engine.signal_validator._backtest_signals) == 1

        # Reset
        engine.reset()

        # All state cleared
        assert len(engine.signal_validator._backtest_signals) == 0
        assert len(engine.execution_tracker._backtest_fills) == 0
        assert len(engine.execution_tracker._live_fills) == 0
        assert not engine.circuit_breaker.is_tripped


class TestShadowBarData:
    """Test ShadowBarData helper class."""

    @pytest.fixture
    def exchange_info(self):
        """Create test exchange info."""
        return ExchangeInfo(
            name="NASDAQ",
            canonical_name="NASDAQ",
            country_code="US",
        )

    @pytest.fixture
    def test_asset(self, exchange_info):
        """Create test asset."""
        return Equity(sid=1, exchange_info=exchange_info, symbol="AAPL")

    @pytest.fixture
    def bar_data(self, test_asset):
        """Create test bar data."""
        market_data = {
            test_asset: {
                "price": Decimal("150.00"),
                "open": Decimal("149.00"),
                "high": Decimal("151.00"),
                "low": Decimal("148.50"),
                "close": Decimal("150.00"),
                "volume": 1000000,
            }
        }
        return ShadowBarData(market_data, datetime.utcnow())

    def test_current_price_field(self, bar_data, test_asset):
        """Test getting current price field."""
        price = bar_data.current(test_asset, "price")
        assert price == Decimal("150.00")

    def test_current_volume_field(self, bar_data, test_asset):
        """Test getting volume field."""
        volume = bar_data.current(test_asset, "volume")
        assert volume == 1000000

    def test_current_ohlc_fields(self, bar_data, test_asset):
        """Test getting OHLC fields."""
        assert bar_data.current(test_asset, "open") == Decimal("149.00")
        assert bar_data.current(test_asset, "high") == Decimal("151.00")
        assert bar_data.current(test_asset, "low") == Decimal("148.50")
        assert bar_data.current(test_asset, "close") == Decimal("150.00")

    def test_current_missing_field(self, bar_data, test_asset):
        """Test getting missing field returns None."""
        result = bar_data.current(test_asset, "missing_field")
        assert result is None

    def test_current_missing_asset(self, bar_data, exchange_info):
        """Test getting data for missing asset returns None."""
        missing_asset = Equity(sid=999, exchange_info=exchange_info, symbol="MISSING")
        result = bar_data.current(missing_asset, "price")
        assert result is None

    def test_can_trade_with_price(self, bar_data, test_asset):
        """Test can_trade returns True when asset has price."""
        assert bar_data.can_trade(test_asset) is True

    def test_can_trade_without_price(self, test_asset):
        """Test can_trade returns False when asset has no price."""
        market_data = {test_asset: {"volume": 1000000}}  # No price
        bar_data = ShadowBarData(market_data, datetime.utcnow())
        assert bar_data.can_trade(test_asset) is False

    def test_can_trade_missing_asset(self, bar_data, exchange_info):
        """Test can_trade returns False for missing asset."""
        missing_asset = Equity(sid=999, exchange_info=exchange_info, symbol="MISSING")
        assert bar_data.can_trade(missing_asset) is False


class TestShadowContext:
    """Test ShadowContext helper class."""

    @pytest.fixture
    def sim_params(self):
        """Create simulation parameters for TradingAlgorithm."""
        return create_simulation_parameters()

    @pytest.fixture
    def asset_finder(self):
        """Create minimal asset finder for testing."""
        finder = Mock(spec=AssetFinder)
        return finder

    @pytest.fixture
    def strategy(self, sim_params, asset_finder):
        """Create strategy with custom context variables."""
        strategy = SimpleBuyStrategy(sim_params=sim_params, asset_finder=asset_finder)
        strategy.custom_var = "test_value"
        strategy.threshold = Decimal("100")
        return strategy

    @pytest.fixture
    def ledger(self):
        """Create test ledger."""
        from rustybt.finance.decimal.ledger import DecimalLedger

        return DecimalLedger(starting_cash=Decimal("100000"))

    @pytest.fixture
    def context(self, ledger, strategy):
        """Create test context."""
        return ShadowContext(ledger, strategy)

    def test_portfolio_property(self, context, ledger):
        """Test portfolio property returns ledger."""
        assert context.portfolio == ledger

    def test_strategy_variables_copied(self, context):
        """Test strategy variables are accessible via context."""
        assert context.custom_var == "test_value"
        assert context.threshold == Decimal("100")

    def test_undefined_attribute_returns_none(self, context):
        """Test undefined attributes return None."""
        result = context.undefined_attribute
        assert result is None
