"""Lighter.xyz broker adapter for live trading.

This module provides integration with Lighter DEX for perpetual futures trading.
Implements secure Ethereum private key management for on-chain authentication.

SECURITY WARNING: This adapter requires an Ethereum private key for authentication.
Never hardcode private keys, commit them to version control, or log them in plaintext.
Use encrypted keystores or environment variables for key management.
"""

import asyncio
import json
import os
import time
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from cryptography.fernet import Fernet

from rustybt.assets import Asset
from rustybt.live.brokers.base import BrokerAdapter

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class TokenBucket:
    """Token bucket rate limiter.

    Implements a token bucket algorithm for rate limiting API requests.
    Tokens are refilled at a constant rate up to a maximum capacity.

    Attributes:
        rate: Tokens added per second
        capacity: Maximum tokens in the bucket
        tokens: Current token count
        last_update: Last time tokens were refilled

    Example:
        >>> bucket = TokenBucket(rate=10.0, capacity=600)  # 10/sec, max 600
        >>> await bucket.acquire()  # Get one token
        >>> await bucket.acquire(5)  # Get five tokens
    """

    def __init__(self, rate: float, capacity: float) -> None:
        """Initialize token bucket.

        Args:
            rate: Tokens per second to add
            capacity: Maximum token capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        async with self._lock:
            while True:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                # Wait for tokens to refill
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False if not enough tokens
        """
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def available(self) -> float:
        """Get current available tokens."""
        self._refill()
        return self.tokens

    def utilization(self) -> float:
        """Get current utilization as percentage (0.0 to 1.0)."""
        self._refill()
        return 1.0 - (self.tokens / self.capacity)

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now


class LighterKeyError(Exception):
    """Lighter private key error.

    Raised when private key cannot be loaded, is invalid, or authentication fails.
    Error messages must never contain sensitive data like the actual key.
    """


class LighterConnectionError(Exception):
    """Lighter connection error.

    Raised when connection to Lighter.xyz API fails or is lost.
    """


class LighterOrderRejectError(Exception):
    """Lighter order rejection error.

    Raised when an order is rejected by the exchange.
    """


class LighterRateLimitError(Exception):
    """Lighter rate limit exceeded error.

    Raised when API rate limits are exceeded.
    """


class LighterBrokerAdapter(BrokerAdapter):
    """Lighter.xyz broker adapter for perpetual futures trading.

    Implements BrokerAdapter interface for Lighter DEX integration.
    Uses lighter-sdk for API communication and transaction signing.

    Supported Order Types:
        - MARKET: Market order
        - LIMIT: Limit order

    Security:
        - Private keys stored encrypted
        - Keys loaded from environment variables or encrypted config
        - Keys never logged in plaintext
        - Supports key rotation

    Network Selection:
        - Testnet (default): For development and testing
        - Mainnet: For production trading

    Example:
        >>> adapter = LighterBrokerAdapter(testnet=True)
        >>> await adapter.connect()
        >>> account = await adapter.get_account_info()
    """

    # API endpoints
    MAINNET_API_URL = "https://mainnet.zklighter.elliot.ai"
    TESTNET_API_URL = "https://testnet.zklighter.elliot.ai"

    # Rate limits (Pattern 2 from Architecture)
    REQUESTS_PER_MINUTE = 600
    ORDERS_PER_SECOND = 20
    RATE_LIMIT_WARNING_THRESHOLD = 0.8  # Warn at 80% utilization

    def __init__(
        self,
        private_key: str | None = None,
        encrypted_key_path: str | None = None,
        encryption_key: str | None = None,
        testnet: bool = True,  # Default to testnet for safety (ADR-003)
        account_index: int = 0,
        api_key_index: int = 0,
        paper_mode: bool = False,
        paper_slippage: Decimal = Decimal("0.001"),  # 0.1% default slippage
    ) -> None:
        """Initialize Lighter broker adapter.

        SECURITY: Provide private key via ONE of these methods:
        1. Environment variable: LIGHTER_PRIVATE_KEY
        2. Encrypted keystore file: encrypted_key_path + encryption_key
        3. Direct (NOT RECOMMENDED): private_key parameter

        Args:
            private_key: Ethereum private key (hex string without 0x prefix)
            encrypted_key_path: Path to encrypted private key file
            encryption_key: Encryption key for encrypted keystore
            testnet: Use testnet if True (default), mainnet if False
            account_index: Lighter account index (default: 0)
            api_key_index: API key index for signing (default: 0)
            paper_mode: If True, simulate orders locally without API calls
            paper_slippage: Slippage for paper market orders (default: 0.1%)

        Raises:
            LighterKeyError: If private key cannot be loaded
            ValueError: If key parameters are invalid
        """
        self._testnet = testnet
        self._account_index = account_index
        self._api_key_index = api_key_index

        # Load private key securely
        self._private_key = self._load_private_key(
            private_key=private_key,
            encrypted_key_path=encrypted_key_path,
            encryption_key=encryption_key,
        )

        # API clients (initialized on connect)
        self._api_client: Any = None
        self._signer_client: Any = None

        # Connection state
        self._connected = False
        self._wallet_address: str | None = None
        self._account_id: str | None = None

        # Market data queue
        self._market_data_queue: asyncio.Queue[dict] = asyncio.Queue()

        # Paper trading mode (Story 10.4.5)
        self._paper_mode = paper_mode
        self._paper_slippage = paper_slippage
        self._paper_order_counter = 0
        self._paper_positions: dict[str, dict] = {}  # symbol -> position
        self._fill_callback: Any = None

        if paper_mode:
            logger.info(
                "paper_mode_enabled",
                slippage=str(paper_slippage),
            )

        # Rate limiters (Pattern 2)
        # 600 requests per minute = 10 per second
        self._request_rate_limiter = TokenBucket(
            rate=self.REQUESTS_PER_MINUTE / 60.0,
            capacity=float(self.REQUESTS_PER_MINUTE),
        )
        # Per-symbol order rate limiters (20 orders/sec per symbol)
        self._order_rate_limiters: dict[str, TokenBucket] = {}

        logger.info(
            "lighter_adapter_initialized",
            testnet=testnet,
            account_index=account_index,
        )

    @property
    def api_url(self) -> str:
        """Get the API URL based on testnet/mainnet selection."""
        return self.TESTNET_API_URL if self._testnet else self.MAINNET_API_URL

    async def connect(self) -> None:
        """Establish connection to Lighter.xyz.

        Initializes API client, verifies credentials by fetching account info,
        and stores wallet address for subsequent operations.

        Raises:
            LighterConnectionError: If connection fails
            LighterKeyError: If credentials are invalid
        """
        if self._connected:
            logger.warning("already_connected")
            return

        logger.info("connecting_to_lighter", testnet=self._testnet, url=self.api_url)

        try:
            # Import lighter SDK
            try:
                import lighter
            except ImportError as e:
                raise LighterConnectionError(
                    "lighter-sdk not installed. Install with: pip install lighter-sdk"
                ) from e

            # Initialize API client (for read operations)
            self._api_client = lighter.ApiClient(url=self.api_url)

            # Derive wallet address from private key
            self._wallet_address = self._derive_wallet_address(self._private_key)

            # Initialize signer client (for authenticated operations)
            self._signer_client = lighter.SignerClient(
                url=self.api_url,
                private_key=self._private_key,
                account_index=self._account_index,
                api_key_index=self._api_key_index,
            )

            # Verify credentials by fetching account info
            account_api = lighter.AccountApi(self._api_client)
            account_info = await account_api.accounts_by_l1_address(l1_address=self._wallet_address)

            if not account_info or not account_info.accounts:
                raise LighterKeyError(
                    "No Lighter account found for this wallet. "
                    "Please ensure you have created an account on Lighter.xyz"
                )

            # Store account ID for later use
            self._account_id = str(account_info.accounts[0].index)

            self._connected = True
            logger.info(
                "connected_to_lighter",
                wallet_address=self._mask_address(self._wallet_address),
                account_id=self._account_id,
                testnet=self._testnet,
            )

        except LighterKeyError:
            # Re-raise key errors as-is
            self._connected = False
            raise
        except Exception as e:
            self._connected = False
            logger.error("connection_failed", error=str(e))
            raise LighterConnectionError(f"Failed to connect to Lighter: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from Lighter.xyz.

        Closes API client connections and cleans up resources.
        """
        if not self._connected:
            logger.warning("not_connected")
            return

        logger.info("disconnecting_from_lighter")

        # Close API client
        if self._api_client:
            try:
                await self._api_client.close()
            except Exception as e:
                logger.warning("api_client_close_error", error=str(e))
            self._api_client = None

        self._signer_client = None
        self._connected = False

        logger.info("disconnected_from_lighter")

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str:
        """Submit order to Lighter.xyz.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: Order type ('market', 'limit')
            limit_price: Limit price for limit orders
            stop_price: Stop price (not supported yet)

        Returns:
            Lighter order ID (format: 'SYMBOL:ORDER_ID')

        Raises:
            LighterOrderRejectError: If order is rejected
            LighterConnectionError: If not connected
            ValueError: If parameters are invalid
        """
        if not self._connected and not self._paper_mode:
            raise LighterConnectionError("Not connected to Lighter.xyz")

        if amount == Decimal("0"):
            raise ValueError("Order amount cannot be zero")

        if stop_price is not None:
            raise ValueError("Stop orders not yet supported")

        # Paper trading mode - simulate locally (Story 10.4.5)
        if self._paper_mode:
            return await self._submit_paper_order(
                asset=asset,
                amount=amount,
                order_type=order_type,
                limit_price=limit_price,
            )

        # Check rate limits (Pattern 2)
        await self._check_request_rate_limit()
        await self._check_order_rate_limit(asset.symbol)

        # Determine side from amount sign (AC5)
        is_buy = amount > Decimal("0")
        side = "buy" if is_buy else "sell"
        quantity = abs(amount)

        # Validate order type and limit price
        if order_type == "limit":
            if limit_price is None:
                raise ValueError("limit_price required for limit orders")
            if limit_price <= Decimal("0"):
                raise ValueError("limit_price must be positive")
        elif order_type != "market":
            raise ValueError(f"Unsupported order type: {order_type}. Supported: 'market', 'limit'")

        try:
            # Submit order via signer client
            if order_type == "market":
                order_result = await self._submit_market_order(
                    symbol=asset.symbol,
                    is_buy=is_buy,
                    quantity=quantity,
                )
            else:  # limit
                order_result = await self._submit_limit_order(
                    symbol=asset.symbol,
                    is_buy=is_buy,
                    quantity=quantity,
                    price=limit_price,
                )

            # Parse order ID from response
            order_id = self._parse_order_id(order_result, asset.symbol)

            logger.info(
                "order_submitted",
                order_id=order_id,
                symbol=asset.symbol,
                side=side,
                order_type=order_type,
                quantity=str(quantity),
                price=str(limit_price) if limit_price else "market",
            )

            return order_id

        except LighterOrderRejectError:
            raise
        except Exception as e:
            logger.error(
                "order_submission_failed",
                symbol=asset.symbol,
                side=side,
                order_type=order_type,
                error=str(e),
            )
            raise LighterOrderRejectError(f"Order submission failed: {e}") from e

    async def _submit_market_order(
        self,
        symbol: str,
        is_buy: bool,
        quantity: Decimal,
    ) -> dict[str, Any]:
        """Submit a market order via lighter-sdk.

        Args:
            symbol: Trading symbol
            is_buy: True for buy, False for sell
            quantity: Order quantity

        Returns:
            API response dict

        Raises:
            LighterOrderRejectError: If order rejected
        """
        if not self._signer_client:
            raise LighterConnectionError("Signer client not initialized")

        try:
            # Use signer client to create and send market order
            result = await self._signer_client.create_market_order(
                order_book=symbol,
                is_bid=is_buy,
                base_amount=int(quantity * Decimal("1e8")),  # Convert to base units
            )
            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "market_order_rejected",
                symbol=symbol,
                side="buy" if is_buy else "sell",
                quantity=str(quantity),
                error=error_msg,
            )
            raise LighterOrderRejectError(f"Market order rejected: {error_msg}") from e

    async def _submit_limit_order(
        self,
        symbol: str,
        is_buy: bool,
        quantity: Decimal,
        price: Decimal,
    ) -> dict[str, Any]:
        """Submit a limit order via lighter-sdk.

        Args:
            symbol: Trading symbol
            is_buy: True for buy, False for sell
            quantity: Order quantity
            price: Limit price

        Returns:
            API response dict

        Raises:
            LighterOrderRejectError: If order rejected
        """
        if not self._signer_client:
            raise LighterConnectionError("Signer client not initialized")

        try:
            # Use signer client to create and send limit order
            result = await self._signer_client.create_order(
                order_book=symbol,
                is_bid=is_buy,
                base_amount=int(quantity * Decimal("1e8")),  # Convert to base units
                price=int(price * Decimal("1e8")),  # Convert to price units
            )
            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "limit_order_rejected",
                symbol=symbol,
                side="buy" if is_buy else "sell",
                quantity=str(quantity),
                price=str(price),
                error=error_msg,
            )
            raise LighterOrderRejectError(f"Limit order rejected: {error_msg}") from e

    def _parse_order_id(self, result: dict[str, Any], symbol: str) -> str:
        """Parse order ID from API response.

        Args:
            result: API response dict
            symbol: Trading symbol

        Returns:
            Order ID in format 'SYMBOL:ORDER_ID'
        """
        # Try various possible response formats
        order_id = (
            result.get("order_id")
            or result.get("id")
            or result.get("orderId")
            or result.get("tx_hash")
        )

        if order_id:
            return f"{symbol}:{order_id}"

        # If no order_id found, check for tx hash or other identifiers
        if "hash" in result:
            return f"{symbol}:{result['hash']}"

        # Generate a placeholder if nothing found
        logger.warning(
            "order_id_not_found_in_response",
            response_keys=list(result.keys()) if isinstance(result, dict) else "not_dict",
        )
        return f"{symbol}:unknown"

    async def _check_request_rate_limit(self) -> None:
        """Check and enforce request rate limit.

        Logs warning at 80% utilization and waits if limit exceeded.
        """
        utilization = self._request_rate_limiter.utilization()

        if utilization >= self.RATE_LIMIT_WARNING_THRESHOLD:
            logger.warning(
                "request_rate_limit_approaching",
                utilization=f"{utilization:.1%}",
                available_tokens=int(self._request_rate_limiter.available()),
            )

        # Acquire a token, waiting if necessary
        await self._request_rate_limiter.acquire(1)

    async def _check_order_rate_limit(self, symbol: str) -> None:
        """Check and enforce order rate limit for a symbol.

        Logs warning at 80% utilization and waits if limit exceeded.

        Args:
            symbol: Trading symbol
        """
        # Get or create rate limiter for this symbol
        if symbol not in self._order_rate_limiters:
            self._order_rate_limiters[symbol] = TokenBucket(
                rate=float(self.ORDERS_PER_SECOND),
                capacity=float(self.ORDERS_PER_SECOND),
            )

        limiter = self._order_rate_limiters[symbol]
        utilization = limiter.utilization()

        if utilization >= self.RATE_LIMIT_WARNING_THRESHOLD:
            logger.warning(
                "order_rate_limit_approaching",
                symbol=symbol,
                utilization=f"{utilization:.1%}",
                available_tokens=int(limiter.available()),
            )

        # Acquire a token, waiting if necessary
        await limiter.acquire(1)

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel an open order on Lighter.xyz.

        Args:
            broker_order_id: Lighter order ID (format: 'SYMBOL:ORDER_ID')

        Raises:
            LighterOrderRejectError: If cancellation fails
            LighterConnectionError: If not connected
            ValueError: If order_id format is invalid
        """
        if not self._connected:
            raise LighterConnectionError("Not connected to Lighter.xyz")

        if not broker_order_id:
            raise ValueError("broker_order_id is required")

        # Parse order ID (format: SYMBOL:ORDER_ID)
        if ":" in broker_order_id:
            symbol, order_id = broker_order_id.split(":", 1)
        else:
            symbol = "unknown"
            order_id = broker_order_id

        # Check rate limit
        await self._check_request_rate_limit()

        try:
            # Use signer client to cancel order
            await self._signer_client.cancel_order(
                order_book=symbol,
                order_id=order_id,
            )

            logger.info(
                "order_cancelled",
                order_id=broker_order_id,
                symbol=symbol,
            )

        except Exception as e:
            logger.error(
                "order_cancel_failed",
                order_id=broker_order_id,
                symbol=symbol,
                error=str(e),
            )
            raise LighterOrderRejectError(f"Cancel failed: {e}") from e

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account balance and margin information from Lighter.xyz.

        Returns:
            Dict with keys:
            - balance: Total account balance
            - available_margin: Available margin for new positions
            - used_margin: Margin used by open positions
            - equity: Total equity

        Raises:
            LighterConnectionError: If not connected or request fails
        """
        if not self._connected:
            raise LighterConnectionError("Not connected to Lighter.xyz")

        # Check rate limit
        await self._check_request_rate_limit()

        try:
            import lighter

            # Query account info via AccountApi
            account_api = lighter.AccountApi(self._api_client)
            response = await account_api.account(
                by="index",
                value=self._account_id,
            )

            # Parse account data (handle both dict and object)
            if isinstance(response, dict):
                data = response
            else:
                data = {
                    "collateral": getattr(response, "collateral", 0),
                    "available_margin": getattr(response, "available_margin", 0),
                    "used_margin": getattr(response, "used_margin", 0),
                    "equity": getattr(response, "equity", 0),
                    "total_pnl": getattr(response, "total_pnl", 0),
                }

            # Convert from base units (1e8) to Decimal
            result = {
                "balance": Decimal(str(data.get("collateral", 0))) / Decimal("1e8"),
                "available_margin": Decimal(str(data.get("available_margin", 0))) / Decimal("1e8"),
                "used_margin": Decimal(str(data.get("used_margin", 0))) / Decimal("1e8"),
                "equity": Decimal(str(data.get("equity", 0))) / Decimal("1e8"),
                "unrealized_pnl": Decimal(str(data.get("total_pnl", 0))) / Decimal("1e8"),
            }

            logger.info(
                "account_info_fetched",
                balance=str(result["balance"]),
                equity=str(result["equity"]),
            )

            return result

        except Exception as e:
            logger.error("get_account_info_failed", error=str(e))
            raise LighterConnectionError(f"Failed to get account info: {e}") from e

    async def get_positions(self) -> list[dict]:
        """Get current positions from Lighter.xyz.

        Returns:
            List of position dicts with keys:
            - symbol: Trading pair symbol
            - size: Position size (signed: positive=long, negative=short)
            - entry_price: Average entry price
            - mark_price: Current mark price
            - unrealized_pnl: Unrealized profit/loss
            - leverage: Position leverage

        Raises:
            LighterConnectionError: If not connected or request fails
        """
        if not self._connected:
            raise LighterConnectionError("Not connected to Lighter.xyz")

        # Check rate limit
        await self._check_request_rate_limit()

        try:
            import lighter

            # Query account positions via AccountApi
            account_api = lighter.AccountApi(self._api_client)
            response = await account_api.account(
                by="index",
                value=self._account_id,
            )

            positions = []
            # Handle positions array
            position_list = (
                getattr(response, "positions", [])
                if not isinstance(response, dict)
                else response.get("positions", [])
            ) or []

            for pos in position_list:
                positions.append(self._parse_position(pos))

            logger.info(
                "positions_fetched",
                count=len(positions),
            )

            return positions

        except Exception as e:
            logger.error("get_positions_failed", error=str(e))
            raise LighterConnectionError(f"Failed to get positions: {e}") from e

    def _parse_position(self, pos: Any) -> dict:
        """Parse Lighter position object to standardized dict.

        Args:
            pos: Lighter position object

        Returns:
            Standardized position dict
        """
        # Get position fields (handle both dict and object access)
        if isinstance(pos, dict):
            symbol = pos.get("order_book") or pos.get("symbol", "unknown")
            size = pos.get("size") or pos.get("base_amount", 0)
            is_long = pos.get("is_long", pos.get("side") != "short")
            entry_price = pos.get("entry_price") or pos.get("avg_entry_price", 0)
            mark_price = pos.get("mark_price", 0)
            unrealized_pnl = pos.get("unrealized_pnl") or pos.get("pnl", 0)
            leverage = pos.get("leverage", 1)
        else:
            symbol = getattr(pos, "order_book", None) or getattr(pos, "symbol", "unknown")
            size = getattr(pos, "size", 0) or getattr(pos, "base_amount", 0)
            is_long = getattr(pos, "is_long", True)
            entry_price = getattr(pos, "entry_price", 0) or getattr(pos, "avg_entry_price", 0)
            mark_price = getattr(pos, "mark_price", 0)
            unrealized_pnl = getattr(pos, "unrealized_pnl", 0) or getattr(pos, "pnl", 0)
            leverage = getattr(pos, "leverage", 1)

        # Convert from base units (1e8) to Decimal
        size_decimal = Decimal(str(size)) / Decimal("1e8") if size else Decimal("0")
        # Apply sign convention: positive=long, negative=short
        if not is_long:
            size_decimal = -abs(size_decimal)

        return {
            "symbol": symbol,
            "size": size_decimal,
            "entry_price": (
                Decimal(str(entry_price)) / Decimal("1e8") if entry_price else Decimal("0")
            ),
            "mark_price": Decimal(str(mark_price)) / Decimal("1e8") if mark_price else Decimal("0"),
            "unrealized_pnl": (
                Decimal(str(unrealized_pnl)) / Decimal("1e8") if unrealized_pnl else Decimal("0")
            ),
            "leverage": Decimal(str(leverage)) if leverage else Decimal("1"),
        }

    async def get_open_orders(self) -> list[dict]:
        """Get all open/pending orders from Lighter.xyz.

        Returns:
            List of order dicts with keys:
            - order_id: str
            - symbol: str
            - side: str ('buy' or 'sell')
            - type: str ('market' or 'limit')
            - quantity: Decimal
            - price: Decimal | None
            - status: str
            - filled_quantity: Decimal
            - timestamp: str

        Raises:
            LighterConnectionError: If not connected or request fails
        """
        if not self._connected:
            raise LighterConnectionError("Not connected to Lighter.xyz")

        # Check rate limit
        await self._check_request_rate_limit()

        try:
            import lighter

            # Query active orders via AccountApi
            account_api = lighter.AccountApi(self._api_client)
            response = await account_api.account_active_orders(
                by="index",
                value=self._account_id,
            )

            orders = []
            for order in getattr(response, "orders", []) or []:
                orders.append(self._parse_order(order))

            logger.info(
                "open_orders_fetched",
                count=len(orders),
            )

            return orders

        except Exception as e:
            logger.error("get_open_orders_failed", error=str(e))
            raise LighterConnectionError(f"Failed to get open orders: {e}") from e

    async def get_order_history(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get order history (filled/cancelled orders) from Lighter.xyz.

        Args:
            limit: Maximum number of orders to return (default: 100)
            offset: Number of orders to skip (default: 0)

        Returns:
            List of order dicts with fill details

        Raises:
            LighterConnectionError: If not connected or request fails
        """
        if not self._connected:
            raise LighterConnectionError("Not connected to Lighter.xyz")

        # Check rate limit
        await self._check_request_rate_limit()

        try:
            import lighter

            # Query inactive (historical) orders via AccountApi
            account_api = lighter.AccountApi(self._api_client)
            response = await account_api.account_inactive_orders(
                by="index",
                value=self._account_id,
                limit=limit,
                offset=offset,
            )

            orders = []
            for order in getattr(response, "orders", []) or []:
                orders.append(self._parse_order(order))

            logger.info(
                "order_history_fetched",
                count=len(orders),
                limit=limit,
                offset=offset,
            )

            return orders

        except Exception as e:
            logger.error("get_order_history_failed", error=str(e))
            raise LighterConnectionError(f"Failed to get order history: {e}") from e

    def _parse_order(self, order: Any) -> dict:
        """Parse Lighter order object to standardized dict.

        Args:
            order: Lighter order object

        Returns:
            Standardized order dict
        """
        # Get order fields (handle both dict and object access)
        if isinstance(order, dict):
            order_id = order.get("id") or order.get("order_id")
            symbol = order.get("order_book") or order.get("symbol", "unknown")
            is_bid = order.get("is_bid", order.get("side") == "buy")
            order_type = order.get("type") or order.get("order_type", "limit")
            base_amount = order.get("base_amount") or order.get("quantity", 0)
            price = order.get("price")
            status = order.get("status", "unknown")
            filled_amount = order.get("filled_amount") or order.get("filled_quantity", 0)
            timestamp = order.get("timestamp") or order.get("created_at", "")
        else:
            order_id = getattr(order, "id", None) or getattr(order, "order_id", None)
            symbol = getattr(order, "order_book", None) or getattr(order, "symbol", "unknown")
            is_bid = getattr(order, "is_bid", True)
            order_type = getattr(order, "type", None) or getattr(order, "order_type", "limit")
            base_amount = getattr(order, "base_amount", 0) or getattr(order, "quantity", 0)
            price = getattr(order, "price", None)
            status = getattr(order, "status", "unknown")
            filled_amount = getattr(order, "filled_amount", 0) or getattr(
                order, "filled_quantity", 0
            )
            timestamp = getattr(order, "timestamp", "") or getattr(order, "created_at", "")

        # Convert base units to Decimal (1e8 = 1.0)
        quantity = Decimal(str(base_amount)) / Decimal("1e8") if base_amount else Decimal("0")
        filled_quantity = (
            Decimal(str(filled_amount)) / Decimal("1e8") if filled_amount else Decimal("0")
        )
        price_decimal = Decimal(str(price)) / Decimal("1e8") if price else None

        return {
            "order_id": f"{symbol}:{order_id}" if order_id else "unknown",
            "symbol": symbol,
            "side": "buy" if is_bid else "sell",
            "type": str(order_type).lower() if order_type else "limit",
            "quantity": quantity,
            "price": price_decimal,
            "status": self._map_lighter_status(status),
            "filled_quantity": filled_quantity,
            "timestamp": str(timestamp),
        }

    # Status mapping constants
    LIGHTER_STATUS_MAP = {
        "pending": "pending",
        "open": "submitted",
        "submitted": "submitted",
        "filled": "filled",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "partially_filled": "partial_fill",
        "partial": "partial_fill",
        "rejected": "rejected",
        "expired": "expired",
    }

    def _map_lighter_status(self, lighter_status: str) -> str:
        """Map Lighter.xyz status to standardized status string.

        Args:
            lighter_status: Status from Lighter API

        Returns:
            Standardized status string
        """
        status_lower = str(lighter_status).lower()
        mapped = self.LIGHTER_STATUS_MAP.get(status_lower)

        if mapped is None:
            logger.warning("unknown_lighter_status", status=lighter_status)
            return "unknown"

        return mapped

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data.

        Args:
            assets: List of assets to subscribe

        Raises:
            LighterConnectionError: If subscription fails
            NotImplementedError: For Story 10.5.4
        """
        # Stub - will be implemented in Story 10.5.4 (Data Adapter)
        raise NotImplementedError("Market data subscription will be implemented in Story 10.5.4")

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data.

        Args:
            assets: List of assets to unsubscribe

        Raises:
            LighterConnectionError: If unsubscribe fails
            NotImplementedError: For Story 10.5.4
        """
        # Stub - will be implemented in Story 10.5.4 (Data Adapter)
        raise NotImplementedError("Market data unsubscription will be implemented in Story 10.5.4")

    async def get_next_market_data(self) -> dict | None:
        """Get next market data update.

        Returns:
            Market data dict or None if queue is empty
        """
        try:
            return await asyncio.wait_for(self._market_data_queue.get(), timeout=0.1)
        except TimeoutError:
            return None

    async def get_current_price(self, asset: Asset) -> Decimal:
        """Get current price for asset.

        Args:
            asset: Asset to get price for

        Returns:
            Current price

        Raises:
            LighterConnectionError: If price fetch fails
            NotImplementedError: For Story 10.5.2
        """
        # Stub - will be implemented in Story 10.5.2 (Data Adapter)
        raise NotImplementedError("Price queries will be implemented in Story 10.5.2")

    def is_connected(self) -> bool:
        """Check if connected to Lighter.xyz.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    # Private methods - Security

    def _load_private_key(
        self,
        private_key: str | None,
        encrypted_key_path: str | None,
        encryption_key: str | None,
    ) -> str:
        """Load private key securely from one of several sources.

        Priority:
        1. Environment variable: LIGHTER_PRIVATE_KEY
        2. Encrypted keystore file
        3. Direct parameter (NOT RECOMMENDED)

        Args:
            private_key: Direct private key (NOT RECOMMENDED)
            encrypted_key_path: Path to encrypted keystore
            encryption_key: Encryption key for keystore

        Returns:
            Ethereum private key (hex string)

        Raises:
            LighterKeyError: If private key cannot be loaded
        """
        # Method 1: Environment variable (RECOMMENDED)
        env_key = os.environ.get("LIGHTER_PRIVATE_KEY")
        if env_key:
            logger.info("private_key_loaded_from_environment")
            return self._validate_private_key(env_key)

        # Method 2: Encrypted keystore file (RECOMMENDED)
        if encrypted_key_path and encryption_key:
            logger.info("loading_private_key_from_encrypted_file")
            return self._load_encrypted_key(encrypted_key_path, encryption_key)

        # Method 3: Direct parameter (NOT RECOMMENDED)
        if private_key:
            logger.warning(
                "private_key_loaded_from_parameter",
                warning="NOT RECOMMENDED - Use environment variable or encrypted keystore",
            )
            return self._validate_private_key(private_key)

        # No key provided
        raise LighterKeyError(
            "No private key provided. Set LIGHTER_PRIVATE_KEY environment variable, "
            "or provide encrypted_key_path + encryption_key"
        )

    def _load_encrypted_key(self, key_path: str, encryption_key: str) -> str:
        """Load private key from encrypted file.

        Args:
            key_path: Path to encrypted key file
            encryption_key: Encryption key

        Returns:
            Decrypted private key

        Raises:
            LighterKeyError: If decryption fails
        """
        try:
            # Read encrypted key
            encrypted_data = Path(key_path).read_bytes()

            # Decrypt
            fernet = Fernet(encryption_key.encode())
            decrypted_data = fernet.decrypt(encrypted_data)

            # Parse JSON
            key_data = json.loads(decrypted_data.decode())
            private_key = key_data.get("private_key")

            if not private_key:
                raise LighterKeyError("No private_key in encrypted file")

            return self._validate_private_key(private_key)

        except LighterKeyError:
            raise
        except Exception as e:
            logger.error("failed_to_load_encrypted_key", error=str(e))
            raise LighterKeyError(f"Failed to load encrypted key: {e}") from e

    def _validate_private_key(self, key: str) -> str:
        """Validate private key format.

        Args:
            key: Private key

        Returns:
            Validated private key (without 0x prefix)

        Raises:
            LighterKeyError: If key is invalid
        """
        # Remove 0x prefix if present
        if key.startswith("0x"):
            key = key[2:]

        # Validate length (64 hex characters = 32 bytes)
        if len(key) != 64:
            raise LighterKeyError(
                f"Invalid private key length: {len(key)}, expected 64 hex characters"
            )

        # Validate hex
        try:
            int(key, 16)
        except ValueError as e:
            raise LighterKeyError("Invalid private key: not a hex string") from e

        return key

    def _derive_wallet_address(self, private_key: str) -> str:
        """Derive wallet address from private key.

        Args:
            private_key: Ethereum private key (hex string without 0x prefix)

        Returns:
            Ethereum wallet address

        Raises:
            LighterKeyError: If address derivation fails
        """
        try:
            from eth_account import Account

            # Create account from private key
            account = Account.from_key(f"0x{private_key}")

            logger.info(
                "wallet_address_derived",
                address=self._mask_address(account.address),
            )

            return account.address

        except ImportError as e:
            raise LighterKeyError(
                "eth-account not installed. Install with: pip install eth-account"
            ) from e
        except Exception as e:
            logger.error("wallet_derivation_failed", error=str(e))
            raise LighterKeyError(f"Failed to derive wallet address: {e}") from e

    @staticmethod
    def _mask_address(address: str) -> str:
        """Mask wallet address for logging.

        Args:
            address: Ethereum address

        Returns:
            Masked address (e.g., 0x1234...abcd)
        """
        if len(address) <= 10:
            return "***"
        return f"{address[:6]}...{address[-4:]}"

    @staticmethod
    def create_encrypted_keystore(private_key: str, output_path: str, encryption_key: str) -> None:
        """Create encrypted keystore file from private key.

        SECURITY: Use this method to create encrypted keystores for production.

        Args:
            private_key: Ethereum private key (hex string)
            output_path: Path to save encrypted keystore
            encryption_key: Encryption key (use Fernet.generate_key())

        Example:
            >>> from cryptography.fernet import Fernet
            >>> encryption_key = Fernet.generate_key().decode()
            >>> LighterBrokerAdapter.create_encrypted_keystore(
            ...     private_key="your_private_key_here",
            ...     output_path="~/.rustybt/lighter_key.enc",
            ...     encryption_key=encryption_key
            ... )
            >>> # Save encryption_key in environment: LIGHTER_ENCRYPTION_KEY
        """
        # Validate key
        if private_key.startswith("0x"):
            private_key = private_key[2:]

        if len(private_key) != 64:
            raise ValueError("Invalid private key length")

        # Validate hex
        try:
            int(private_key, 16)
        except ValueError as e:
            raise ValueError("Invalid private key: not a hex string") from e

        # Create key data
        key_data = {
            "private_key": private_key,
            "created_at": str(asyncio.get_event_loop().time()),
        }

        # Encrypt
        fernet = Fernet(encryption_key.encode())
        encrypted_data = fernet.encrypt(json.dumps(key_data).encode())

        # Write to file
        output = Path(output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(encrypted_data)

        logger.info("encrypted_keystore_created", path=str(output))

    # Paper Trading Methods (Story 10.4.5)

    async def _submit_paper_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None,
    ) -> str:
        """Submit simulated paper order locally.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: Order type ('market', 'limit')
            limit_price: Limit price for limit orders

        Returns:
            Simulated order ID (format: 'PAPER-XXXXXX')
        """
        from datetime import datetime, timezone

        # Generate simulated order ID
        self._paper_order_counter += 1
        order_id = f"PAPER-{self._paper_order_counter:06d}"

        # Determine side
        is_buy = amount > Decimal("0")
        side = "buy" if is_buy else "sell"
        quantity = abs(amount)

        # Calculate fill price
        if order_type == "market":
            # For paper mode, use limit price as market price if available
            # Otherwise use a placeholder (real implementation would fetch real price)
            if limit_price is not None:
                base_price = limit_price
            else:
                # In paper mode without price, we need a price
                # This would normally come from market data
                base_price = Decimal("50000")  # Placeholder

            # Apply slippage for market orders
            if is_buy:
                fill_price = base_price * (Decimal("1") + self._paper_slippage)
            else:
                fill_price = base_price * (Decimal("1") - self._paper_slippage)
        else:  # limit
            if limit_price is None:
                raise ValueError("limit_price required for limit orders")
            fill_price = limit_price

        # Generate simulated fill
        fill_data = {
            "order_id": f"{asset.symbol}:{order_id}",
            "symbol": asset.symbol,
            "side": side,
            "fill_price": fill_price,
            "fill_quantity": quantity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Log paper trade
        logger.info(
            "paper_trade_executed",
            order_id=order_id,
            symbol=asset.symbol,
            side=side.upper(),
            order_type=order_type,
            quantity=str(quantity),
            fill_price=str(fill_price),
        )

        # Update paper position
        await self._update_paper_position(
            symbol=asset.symbol,
            quantity=amount,  # Signed amount
            fill_price=fill_price,
        )

        # Trigger fill callback if registered
        if self._fill_callback:
            await self._fill_callback(fill_data)

        return f"{asset.symbol}:{order_id}"

    async def _update_paper_position(
        self,
        symbol: str,
        quantity: Decimal,
        fill_price: Decimal,
    ) -> None:
        """Update paper position after simulated fill.

        Args:
            symbol: Trading symbol
            quantity: Fill quantity (signed: positive=buy, negative=sell)
            fill_price: Fill price
        """
        if symbol in self._paper_positions:
            pos = self._paper_positions[symbol]
            old_size = pos["size"]
            old_entry = pos["entry_price"]

            # Calculate new position
            new_size = old_size + quantity

            if new_size == Decimal("0"):
                # Position closed
                del self._paper_positions[symbol]
            else:
                # Update average entry price (weighted average)
                if (old_size > 0 and quantity > 0) or (old_size < 0 and quantity < 0):
                    # Adding to position
                    total_cost = old_size * old_entry + quantity * fill_price
                    new_entry = total_cost / new_size
                else:
                    # Reducing or reversing position
                    if abs(new_size) <= abs(quantity):
                        # Reversed position
                        new_entry = fill_price
                    else:
                        # Partially reduced
                        new_entry = old_entry

                self._paper_positions[symbol] = {
                    "size": new_size,
                    "entry_price": new_entry,
                    "mark_price": fill_price,  # Use fill price as current mark
                }
        else:
            # New position
            self._paper_positions[symbol] = {
                "size": quantity,
                "entry_price": fill_price,
                "mark_price": fill_price,
            }

        logger.debug(
            "paper_position_updated",
            symbol=symbol,
            new_size=str(self._paper_positions.get(symbol, {}).get("size", 0)),
        )

    def set_fill_callback(self, callback: Any) -> None:
        """Set callback for fill notifications.

        Args:
            callback: Async callback function that receives fill data dict
        """
        self._fill_callback = callback
        logger.info("fill_callback_registered")

    @property
    def paper_mode(self) -> bool:
        """Check if paper trading mode is enabled."""
        return self._paper_mode

    def get_paper_positions(self) -> dict[str, dict]:
        """Get paper trading positions.

        Returns:
            Dict of symbol -> position data (only in paper mode)
        """
        if not self._paper_mode:
            return {}
        return self._paper_positions.copy()
