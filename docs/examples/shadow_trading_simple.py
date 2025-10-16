# ruff: noqa
"""Simple shadow trading validation example.

This example demonstrates the shadow trading framework components working together
to validate backtest-live alignment.

Usage:
    python examples/shadow_trading_simple.py
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from rustybt.assets import Equity, ExchangeInfo
from rustybt.live.shadow import (
    AlignmentCircuitBreaker,
    ExecutionQualityTracker,
    ShadowTradingConfig,
    SignalAlignmentValidator,
    SignalRecord,
)


async def main():
    """Demonstrate shadow trading validation."""
    print("=" * 80)
    print("SHADOW TRADING VALIDATION EXAMPLE")
    print("=" * 80)
    print()

    # Setup
    exchange = ExchangeInfo("NASDAQ", "NASDAQ", "US")
    aapl = Equity(1, exchange, symbol="AAPL")

    # Create configuration (paper trading = strict thresholds)
    config = ShadowTradingConfig.for_paper_trading()
    print("Configuration:")
    print(f"  Signal match rate min: {config.signal_match_rate_min:.1%}")
    print(f"  Slippage error max:    {config.slippage_error_bps_max} bps")
    print(f"  Fill rate error max:   {config.fill_rate_error_pct_max}%")
    print(f"  Time tolerance:        {config.time_tolerance_ms}ms")
    print(f"  Grace period:          {config.grace_period_seconds}s")
    print()

    # Create shadow trading components
    signal_validator = SignalAlignmentValidator(config)
    ExecutionQualityTracker(config)
    circuit_breaker = AlignmentCircuitBreaker(config)

    # Simulate trading scenario
    print("Simulating trading scenario...")
    print()

    base_time = datetime.utcnow()
    scenarios = [
        # Scenario 1: Perfect alignment (EXACT_MATCH)
        {
            "name": "Perfect Alignment",
            "backtest": SignalRecord(
                timestamp=base_time,
                asset=aapl,
                side="BUY",
                quantity=Decimal("100"),
                price=Decimal("150.00"),
                order_type="market",
                source="backtest",
            ),
            "live": SignalRecord(
                timestamp=base_time + timedelta(milliseconds=30),
                asset=aapl,
                side="BUY",
                quantity=Decimal("100"),
                price=Decimal("150.00"),
                order_type="market",
                source="live",
            ),
        },
        # Scenario 2: Direction match with small quantity difference
        {
            "name": "Direction Match (5% qty diff)",
            "backtest": SignalRecord(
                timestamp=base_time + timedelta(seconds=10),
                asset=aapl,
                side="BUY",
                quantity=Decimal("100"),
                price=Decimal("151.00"),
                order_type="market",
                source="backtest",
            ),
            "live": SignalRecord(
                timestamp=base_time + timedelta(seconds=10, milliseconds=40),
                asset=aapl,
                side="BUY",
                quantity=Decimal("105"),  # 5% more
                price=Decimal("151.00"),
                order_type="market",
                source="live",
            ),
        },
        # Scenario 3: Magnitude mismatch (large quantity difference)
        {
            "name": "Magnitude Mismatch (100% qty diff)",
            "backtest": SignalRecord(
                timestamp=base_time + timedelta(seconds=20),
                asset=aapl,
                side="SELL",
                quantity=Decimal("100"),
                price=Decimal("152.00"),
                order_type="market",
                source="backtest",
            ),
            "live": SignalRecord(
                timestamp=base_time + timedelta(seconds=20, milliseconds=45),
                asset=aapl,
                side="SELL",
                quantity=Decimal("200"),  # 100% more
                price=Decimal("152.00"),
                order_type="market",
                source="live",
            ),
        },
    ]

    # Process scenarios
    for i, scenario in enumerate(scenarios, 1):
        print(f"Scenario {i}: {scenario['name']}")

        # Add backtest signal
        signal_validator.add_backtest_signal(scenario["backtest"])

        # Add live signal (triggers matching)
        result = signal_validator.add_live_signal(scenario["live"])

        if result:
            matched_signal, alignment = result
            print(
                f"  Backtest: {scenario['backtest'].side} {scenario['backtest'].quantity} @ ${scenario['backtest'].price}"
            )
            print(
                f"  Live:     {scenario['live'].side} {scenario['live'].quantity} @ ${scenario['live'].price}"
            )
            print(f"  Alignment: {alignment.value.upper()}")
        else:
            print("  ❌ No match found (MISSING_SIGNAL)")

        print()

    # Calculate alignment metrics
    print("-" * 80)
    print("Alignment Metrics")
    print("-" * 80)
    print()

    match_rate = signal_validator.calculate_match_rate(window_minutes=60)
    divergence_breakdown = signal_validator.get_divergence_breakdown()

    print(f"Signal match rate: {match_rate:.1%}")
    print()
    print("Divergence breakdown:")
    for alignment, count in divergence_breakdown.items():
        print(f"  {alignment.value}: {count}")
    print()

    # Check alignment (circuit breaker)
    print("-" * 80)
    print("Circuit Breaker Check")
    print("-" * 80)
    print()

    # Calculate metrics for circuit breaker check
    from rustybt.live.shadow.models import AlignmentMetrics, ExecutionQualityMetrics

    # Create execution quality metrics (empty for this demo)
    exec_quality = ExecutionQualityMetrics(
        expected_slippage_bps=Decimal("0"),
        actual_slippage_bps=Decimal("0"),
        slippage_error_bps=Decimal("0"),
        fill_rate_expected=Decimal("1"),
        fill_rate_actual=Decimal("1"),
        fill_rate_error_pct=Decimal("0"),
        commission_expected=Decimal("0"),
        commission_actual=Decimal("0"),
        commission_error_pct=Decimal("0"),
        sample_count=0,
    )

    alignment_metrics = AlignmentMetrics(
        execution_quality=exec_quality,
        backtest_signal_count=len(signal_validator._backtest_signals),
        live_signal_count=len(signal_validator._live_signals),
        signal_match_rate=match_rate,
        divergence_breakdown=divergence_breakdown,
    )

    is_aligned = circuit_breaker.check_alignment(alignment_metrics)

    if is_aligned:
        print("✅ Alignment is good - trading continues")
    else:
        breach_summary = circuit_breaker.get_breach_summary()
        print(f"❌ Circuit breaker tripped: {breach_summary}")
        print()
        print("Trading has been halted for manual investigation.")

    print()

    # Get full alignment metrics
    metrics = alignment_metrics.to_dict()

    print("-" * 80)
    print("Complete Alignment Metrics (JSON)")
    print("-" * 80)
    print()

    import json

    print(json.dumps(metrics, indent=2))

    print()
    print("=" * 80)
    print("Shadow trading validation complete!")
    print()
    print("In production, these metrics would be:")
    print("  1. Persisted in StateManager checkpoints")
    print("  2. Displayed in real-time dashboard")
    print("  3. Used to trip circuit breakers when thresholds breached")
    print("  4. Analyzed for trend detection and model drift")
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
