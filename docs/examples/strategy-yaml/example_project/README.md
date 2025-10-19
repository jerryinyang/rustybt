# Momentum Strategy Example

This is an example strategy demonstrating explicit code capture using `strategy.yaml`.

## Files

- `my_strategy.py` - Main strategy implementation
- `utils/indicators.py` - Technical indicators
- `utils/risk.py` - Risk management
- `config/params.json` - Strategy parameters
- `strategy.yaml` - Code capture configuration

## How It Works

When you run a backtest with this strategy, RustyBT will:

1. Detect `strategy.yaml` in the strategy directory
2. Copy all files listed in `strategy.yaml` to the backtest output directory
3. Preserve the directory structure

The captured code will be stored in:
```
backtests/{backtest_id}/code/
├── my_strategy.py
├── utils/
│   ├── indicators.py
│   └── risk.py
├── config/
│   └── params.json
└── README.md
```

This ensures complete reproducibility of your backtest.
