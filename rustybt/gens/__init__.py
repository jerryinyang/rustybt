"""Event generators and simulation infrastructure for backtesting.

This module provides core simulation components including:
- Clock abstractions (SimulationClock, LiveClock)
- Event systems with priority handling
- Temporal isolation for preventing lookahead bias
- Trade simulation and algorithm execution

Examples:
    Create a simulation clock for backtesting::

        import pandas as pd
        from rustybt.gens.clock import SimulationClock

        clock = SimulationClock(
            start=pd.Timestamp('2023-01-01'),
            end=pd.Timestamp('2023-12-31'),
            resolution='daily'
        )

        for dt in clock:
            print(f"Processing {dt}")
"""
