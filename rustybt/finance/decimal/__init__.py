"""Decimal-based financial calculations for RustyBT.

This module provides Decimal-precision financial calculations for
portfolio management, order execution, and performance metrics.
"""

from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.commission import (
    CryptoCommission,
    DecimalCommissionModel,
    NoCommission,
    PerDollarCommission,
    PerShareCommission,
    PerTradeCommission,
)
from rustybt.finance.decimal.config import (
    DecimalConfig,
    DecimalConfigError,
    InvalidAssetClassError,
    InvalidPrecisionError,
    InvalidRoundingModeError,
)
from rustybt.finance.decimal.ledger import (
    DecimalLedger,
    InsufficientFundsError,
    InvalidTransactionError,
    LedgerError,
)
from rustybt.finance.decimal.order import (
    DecimalOrder,
    InsufficientPrecisionError,
    InvalidPriceError,
    InvalidQuantityError,
    OrderError,
)
from rustybt.finance.decimal.position import (
    DecimalPosition,
    InvalidPositionError,
    PositionError,
)
from rustybt.finance.decimal.slippage import (
    AsymmetricSlippage,
    DecimalSlippageModel,
    FixedBasisPointsSlippage,
    FixedSlippage,
    NoSlippage,
    VolumeShareSlippage,
)
from rustybt.finance.decimal.transaction import DecimalTransaction, create_decimal_transaction

__all__ = [
    # Config
    "DecimalConfig",
    "DecimalConfigError",
    "InvalidAssetClassError",
    "InvalidPrecisionError",
    "InvalidRoundingModeError",
    # Ledger and Position
    "DecimalLedger",
    "DecimalPosition",
    "InsufficientFundsError",
    "InvalidPositionError",
    "InvalidTransactionError",
    "LedgerError",
    "PositionError",
    # Order execution
    "DecimalBlotter",
    "DecimalOrder",
    "DecimalTransaction",
    "create_decimal_transaction",
    "InsufficientPrecisionError",
    "InvalidPriceError",
    "InvalidQuantityError",
    "OrderError",
    # Commission models
    "CryptoCommission",
    "DecimalCommissionModel",
    "NoCommission",
    "PerDollarCommission",
    "PerShareCommission",
    "PerTradeCommission",
    # Slippage models
    "AsymmetricSlippage",
    "DecimalSlippageModel",
    "FixedBasisPointsSlippage",
    "FixedSlippage",
    "NoSlippage",
    "VolumeShareSlippage",
]
