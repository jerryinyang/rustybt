"""Type stubs for rustybt.protocol - Portfolio, Account, Position classes.

Provides type hints for IDE autocomplete and type checking when writing
trading strategies that access portfolio state, account information, and positions.
"""

from typing import Dict

import pandas as pd

from rustybt._protocol import InnerPosition
from rustybt.assets import Asset

class Portfolio:
    """Portfolio state with read-only access.

    Provides current portfolio valuation, positions, and performance metrics.
    Accessible in strategies via context.portfolio.

    Attributes
    ----------
    cash : float
        Current cash balance in portfolio.
    portfolio_value : float
        Total portfolio value (cash + positions_value).
    starting_cash : float
        Initial cash balance at start of backtest.
    pnl : float
        Profit and loss since start.
    returns : float
        Returns since start.
    positions_value : float
        Total value of all positions (sum of position market values).
    positions_exposure : float
        Total exposure of all positions.
    cash_flow : float
        Net cash flow (same as capital_used).
    positions : Dict[Asset, Position]
        Dictionary mapping assets to their positions.
    start_date : pd.Timestamp
        Start date of the portfolio.
    """

    cash: float
    portfolio_value: float
    starting_cash: float
    pnl: float
    returns: float
    positions_value: float
    positions_exposure: float
    cash_flow: float
    positions: Dict[Asset, Position]
    start_date: pd.Timestamp

    def __init__(
        self, start_date: pd.Timestamp | None = None, capital_base: float = 0.0
    ) -> None: ...
    @property
    def capital_used(self) -> float: ...
    @property
    def current_portfolio_weights(self) -> pd.Series: ...

class Account:
    """Trading account state with read-only access.

    Tracks margin requirements, buying power, leverage, and other account metrics.
    Accessible in strategies via context.account.

    Attributes
    ----------
    settled_cash : float
        Cash that has settled and is available for trading.
    accrued_interest : float
        Accrued interest on account.
    buying_power : float
        Available buying power for new positions.
    equity_with_loan : float
        Total equity including borrowed funds.
    total_positions_value : float
        Total value of all positions.
    total_positions_exposure : float
        Total exposure of all positions.
    regt_equity : float
        Regulation T equity.
    regt_margin : float
        Regulation T margin.
    initial_margin_requirement : float
        Initial margin requirement.
    maintenance_margin_requirement : float
        Maintenance margin requirement.
    available_funds : float
        Funds available for trading.
    excess_liquidity : float
        Excess liquidity in account.
    cushion : float
        Cushion (excess_liquidity / net_liquidation).
    day_trades_remaining : float
        Number of day trades remaining.
    leverage : float
        Current leverage ratio.
    net_leverage : float
        Net leverage (long - short).
    net_liquidation : float
        Net liquidation value.
    """

    settled_cash: float
    accrued_interest: float
    buying_power: float
    equity_with_loan: float
    total_positions_value: float
    total_positions_exposure: float
    regt_equity: float
    regt_margin: float
    initial_margin_requirement: float
    maintenance_margin_requirement: float
    available_funds: float
    excess_liquidity: float
    cushion: float
    day_trades_remaining: float
    leverage: float
    net_leverage: float
    net_liquidation: float

    def __init__(self) -> None: ...

class Position:
    """Position in a single asset with read-only access.

    Represents a held position in the portfolio.
    Accessible via context.portfolio.positions[asset].

    Attributes
    ----------
    asset : Asset
        The asset being held.
    amount : int
        Number of shares/contracts held (negative for short positions).
    cost_basis : float
        Average price paid for currently-held shares.
    last_sale_price : float
        Most recent price for this position.
    last_sale_date : pd.Timestamp
        Timestamp of the last sale price update.
    """

    asset: Asset
    amount: int
    cost_basis: float
    last_sale_price: float
    last_sale_date: pd.Timestamp

    def __init__(self, underlying_position: InnerPosition) -> None: ...
    @property
    def sid(self) -> int: ...

class Positions:
    """Dict-like container for positions.

    Provides dictionary-style access to positions by asset.
    """

    def __contains__(self, asset: Asset) -> bool: ...
    def __getitem__(self, asset: Asset) -> Position: ...
    def __iter__(self): ...
    def __len__(self) -> int: ...
    def items(self): ...
    def keys(self): ...
    def values(self): ...
