"""Main entry point for YAML-configured strategy."""

import json
from pathlib import Path

from custom_helpers import calculate_signal

from rustybt import run_algorithm


def initialize(context):
    """Initialize strategy from JSON config."""
    # Load parameters from JSON
    params_path = Path(__file__).parent / "config" / "params.json"
    with open(params_path) as f:
        context.params = json.load(f)

    context.symbols = context.params["symbols"]


def handle_data(context, data):
    """Handle market data."""
    for symbol in context.symbols:
        signal = calculate_signal(symbol, context.params["threshold"])
        if signal > 0:
            # order(symbol, 100)
            pass


if __name__ == "__main__":
    # Entry point
    run_algorithm(
        start="2020-01-01",
        end="2020-12-31",
        initialize=initialize,
        handle_data=handle_data,
        capital_base=100000,
    )
