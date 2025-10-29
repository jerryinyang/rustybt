"""Type stubs for rustybt.assets.continuous_futures - Compiled Cython module."""

from typing import Any, Callable, Optional
import pandas as pd
from rustybt.assets.exchange_info import ExchangeInfo

def delivery_predicate(codes: set[str], contract: Any) -> bool: ...

march_cycle_delivery_predicate: Callable[[Any], bool]

CHAIN_PREDICATES: dict[str, Callable[[Any], bool]]
ADJUSTMENT_STYLES: set[Optional[str]]

class ContinuousFuture:
    """Represents a specifier for a chain of future contracts.

    Attributes
    ----------
    sid : int
        Persistent unique identifier.
    root_symbol : str
        The root symbol of the contracts.
    offset : int
        The distance from the primary chain (0=primary, 1=secondary, etc).
    roll_style : str
        How rolls from contract to contract should be calculated.
    start_date : pd.Timestamp
        Start date for the continuous future.
    end_date : pd.Timestamp
        End date for the continuous future.
    exchange_info : ExchangeInfo
        Exchange information.
    adjustment : str or None
        Adjustment style ('add', 'mul', or None).
    """

    sid: int
    root_symbol: str
    offset: int
    roll_style: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    exchange_info: ExchangeInfo
    adjustment: Optional[str]

    @property
    def exchange(self) -> str: ...
    @property
    def exchange_full(self) -> str: ...

    def __init__(
        self,
        sid: int,
        root_symbol: str,
        offset: int,
        roll_style: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        exchange_info: ExchangeInfo,
        adjustment: Optional[str] = None,
    ) -> None: ...

    def __int__(self) -> int: ...
    def __index__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, other: object) -> bool: ...
    def __lt__(self, other: Any) -> bool: ...
    def __le__(self, other: Any) -> bool: ...
    def __gt__(self, other: Any) -> bool: ...
    def __ge__(self, other: Any) -> bool: ...
    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...

class ContractNode:
    """Node in a linked list of future contracts."""

    contract: Any
    next_contract: Optional["ContractNode"]

    def __init__(self, contract: Any, next_contract: Optional["ContractNode"] = None) -> None: ...

class OrderedContracts:
    """Linked list of future contracts in delivery order."""

    root_symbol: str
    contracts: list[Any]

    def __init__(self, root_symbol: str, contracts: list[Any]) -> None: ...

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> Any: ...
    def active_chain(self, start_date: pd.Timestamp, end_date: pd.Timestamp, offset: int) -> list[Any]: ...
    def contract_before_auto_close(self, dt: pd.Timestamp) -> Optional[Any]: ...
    def contract_at_offset(self, start_contract: Any, offset: int, start_cap: pd.Timestamp) -> Optional[Any]: ...
