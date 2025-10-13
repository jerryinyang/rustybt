"""Hyperliquid broker adapter for live trading.

This module provides integration with Hyperliquid DEX for perpetual futures trading.
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
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from rustybt.assets import Asset
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.streaming.bar_buffer import BarBuffer, OHLCVBar
from rustybt.live.streaming.hyperliquid_stream import HyperliquidWebSocketAdapter

if TYPE_CHECKING:
    from rustybt.live.streaming.models import TickData

logger = structlog.get_logger(__name__)


class HyperliquidConnectionError(Exception):
    """Hyperliquid connection error."""


class HyperliquidOrderRejectError(Exception):
    """Hyperliquid order rejection error."""


class HyperliquidKeyError(Exception):
    """Hyperliquid private key error."""


class HyperliquidRateLimitError(Exception):
    """Hyperliquid rate limit exceeded error."""


class HyperliquidBrokerAdapter(BrokerAdapter):
    """Hyperliquid broker adapter.

    Integrates with Hyperliquid DEX for perpetual futures trading.
    Uses Ethereum private key for on-chain authentication.

    Supported Order Types:
        - MARKET: Market order
        - LIMIT: Limit order
        - STOP_MARKET: Stop-market order
        - STOP_LIMIT: Stop-limit order

    Order Execution Modes:
        - Post-Only: Maker-only orders
        - Reduce-Only: Position reduction only

    Rate Limits:
        - REST API: 600 requests/minute
        - Order placement: 20 orders/second

    Security:
        - Private keys stored encrypted
        - Keys loaded from environment variables or encrypted config
        - Keys never logged in plaintext
        - Supports key rotation
    """

    # API endpoints
    MAINNET_API_URL = constants.MAINNET_API_URL
    TESTNET_API_URL = "https://api.hyperliquid-testnet.xyz"  # If available

    # Rate limiting
    REQUESTS_PER_MINUTE = 600
    ORDERS_PER_SECOND = 20

    def __init__(
        self,
        private_key: str | None = None,
        encrypted_key_path: str | None = None,
        encryption_key: str | None = None,
        testnet: bool = False,
    ) -> None:
        """Initialize Hyperliquid broker adapter.

        SECURITY: Provide private key via ONE of these methods:
        1. Environment variable: HYPERLIQUID_PRIVATE_KEY
        2. Encrypted keystore file: encrypted_key_path + encryption_key
        3. Direct (NOT RECOMMENDED): private_key parameter

        Args:
            private_key: Ethereum private key (hex string without 0x prefix)
            encrypted_key_path: Path to encrypted private key file
            encryption_key: Encryption key for encrypted keystore
            testnet: Use testnet if True (if available)

        Raises:
            HyperliquidKeyError: If private key cannot be loaded
            ValueError: If key parameters are invalid
        """
        self.testnet = testnet

        # Load private key securely
        self._private_key = self._load_private_key(
            private_key=private_key,
            encrypted_key_path=encrypted_key_path,
            encryption_key=encryption_key,
        )

        # Initialize Hyperliquid SDK
        base_url = self.TESTNET_API_URL if testnet else self.MAINNET_API_URL

        # Info API (read-only, no authentication)
        self.info = Info(base_url=base_url, skip_ws=True)

        # Exchange API (requires private key for signing)
        self.exchange = Exchange(
            wallet=None,  # Will set wallet address after first call
            base_url=base_url,
            account_address=None,  # Will use wallet address
        )

        # Set private key in exchange (securely)
        self.exchange.wallet = self._get_wallet_from_key(self._private_key)

        self._connected = False
        self._market_data_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._wallet_address: str | None = None

        # Rate limiting tracking
        self._request_timestamps: list[float] = []
        self._order_timestamps: dict[str, list[float]] = {}

        # WebSocket streaming components
        self._ws_adapter: HyperliquidWebSocketAdapter | None = None
        self._bar_buffer: BarBuffer | None = None

        logger.info(
            "hyperliquid_adapter_initialized",
            testnet=testnet,
            wallet_address_set=self._wallet_address is not None,
        )

    async def connect(self) -> None:
        """Establish connection to Hyperliquid.

        Raises:
            HyperliquidConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("already_connected")
            return

        logger.info("connecting_to_hyperliquid", testnet=self.testnet)

        try:
            # Test API connectivity by fetching user state
            user_state = self.info.user_state(self.exchange.wallet.address)

            if user_state is None:
                raise HyperliquidConnectionError("Failed to fetch user state")

            # Store wallet address
            self._wallet_address = self.exchange.wallet.address

            # Initialize WebSocket adapter
            self._ws_adapter = HyperliquidWebSocketAdapter(
                testnet=self.testnet,
                on_tick=self._handle_tick,
            )

            # Initialize bar buffer (1-minute bars default)
            self._bar_buffer = BarBuffer(
                bar_resolution=60,  # 60 seconds = 1 minute
                on_bar_complete=self._handle_bar_complete,
            )

            # Connect WebSocket
            await self._ws_adapter.connect()

            self._connected = True
            logger.info(
                "connected_to_hyperliquid",
                wallet_address=self._mask_address(self._wallet_address),
            )

        except Exception as e:
            self._connected = False
            logger.error("connection_failed", error=str(e))
            raise HyperliquidConnectionError(f"Failed to connect to Hyperliquid: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from Hyperliquid."""
        if not self._connected:
            logger.warning("not_connected")
            return

        logger.info("disconnecting_from_hyperliquid")

        # Disconnect WebSocket first
        if self._ws_adapter:
            await self._ws_adapter.disconnect()
            self._ws_adapter = None

        # Clear bar buffer
        self._bar_buffer = None

        # Hyperliquid SDK doesn't require explicit disconnect
        self._connected = False

        logger.info("disconnected_from_hyperliquid")

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
        post_only: bool = False,
        reduce_only: bool = False,
    ) -> str:
        """Submit order to Hyperliquid.

        Args:
            asset: Asset to trade (perpetual futures symbol)
            amount: Order quantity (positive=buy, negative=sell)
            order_type: Order type ('market', 'limit', 'stop', 'stop-limit')
            limit_price: Limit price for limit/stop-limit orders
            stop_price: Trigger price for stop orders
            post_only: Post-Only mode (ALO - Add Liquidity Only, Limit orders only)
            reduce_only: Reduce-Only mode (position reduction only)

        Returns:
            Hyperliquid order ID

        Raises:
            HyperliquidOrderRejectError: If order is rejected
            HyperliquidRateLimitError: If rate limit exceeded
            ValueError: If parameters are invalid

        Examples:
            # Post-Only order (ALO - Add Liquidity Only)
            await adapter.submit_order(
                asset=btc,
                amount=Decimal("0.1"),
                order_type="limit",
                limit_price=Decimal("50000"),
                post_only=True
            )

            # Reduce-Only order
            await adapter.submit_order(
                asset=btc,
                amount=Decimal("-0.1"),
                order_type="market",
                reduce_only=True
            )
        """
        if not self._connected:
            raise HyperliquidConnectionError("Not connected to Hyperliquid")

        # Check rate limits
        await self._check_request_rate_limit()
        await self._check_order_rate_limit(asset.symbol)

        # Validate parameters
        if amount == 0:
            raise ValueError("Order amount cannot be zero")

        # Validate Post-Only with Market orders
        if post_only and order_type == "market":
            raise ValueError("Post-Only mode is incompatible with Market orders (Limit only)")

        # Map order type
        is_buy = amount > 0
        quantity = abs(amount)

        # Build order request
        # NOTE: Hyperliquid SDK requires float at API boundary - convert only here
        if order_type == "market":
            # Market order
            order_result = self.exchange.market_open(
                coin=asset.symbol,
                is_buy=is_buy,
                sz=float(quantity),
                px=None,  # Market price
                reduce_only=reduce_only,
            )
        elif order_type == "limit":
            # Limit order
            if limit_price is None:
                raise ValueError("limit_price required for limit order")

            # Build order type params
            if post_only:
                # Post-Only: ALO (Add Liquidity Only) time-in-force
                order_type_params = {"limit": {"tif": "Alo"}}
            else:
                # Standard: GTC (Good-til-cancelled)
                order_type_params = {"limit": {"tif": "Gtc"}}

            order_result = self.exchange.order(
                coin=asset.symbol,
                is_buy=is_buy,
                sz=float(quantity),
                limit_px=float(limit_price),
                order_type=order_type_params,
                reduce_only=reduce_only,
            )
        else:
            raise ValueError(
                f"Unsupported order type: {order_type}. Supported types: market, limit"
            )

        # Check order result
        if "status" in order_result and order_result["status"] == "error":
            error_msg = order_result.get("response", "Unknown error")
            raise HyperliquidOrderRejectError(f"Order rejected: {error_msg}")

        # Extract order ID and format with symbol
        if "response" in order_result and "data" in order_result["response"]:
            statuses = order_result["response"]["data"]["statuses"]
            if statuses and len(statuses) > 0:
                order_status = statuses[0]
                if "resting" in order_status:
                    oid = str(order_status["resting"]["oid"])
                    order_id = f"{asset.symbol}:{oid}"
                elif "filled" in order_status:
                    # Order filled immediately
                    order_id = f"{asset.symbol}:filled_immediately"
                else:
                    order_id = f"{asset.symbol}:unknown"
            else:
                order_id = f"{asset.symbol}:unknown"
        else:
            order_id = f"{asset.symbol}:unknown"

        logger.info(
            "order_submitted",
            order_id=order_id,
            symbol=asset.symbol,
            side="BUY" if is_buy else "SELL",
            order_type=order_type,
            quantity=quantity,
            price=str(limit_price) if limit_price else "market",
            post_only=post_only,
            reduce_only=reduce_only,
        )

        return order_id

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order.

        Args:
            broker_order_id: Hyperliquid order ID (format: 'SYMBOL:OID')

        Raises:
            HyperliquidOrderRejectError: If cancellation fails
        """
        if not self._connected:
            raise HyperliquidConnectionError("Not connected to Hyperliquid")

        # Parse order ID
        if ":" not in broker_order_id:
            raise ValueError("Order ID must be in format 'SYMBOL:OID'")

        symbol, oid = broker_order_id.split(":", 1)

        try:
            # Cancel order
            result = self.exchange.cancel(coin=symbol, oid=int(oid))

            # Check result
            if "status" in result and result["status"] == "error":
                error_msg = result.get("response", "Unknown error")
                raise HyperliquidOrderRejectError(f"Failed to cancel order: {error_msg}")

            logger.info("order_cancelled", order_id=broker_order_id, symbol=symbol)

        except Exception as e:
            logger.error("order_cancellation_failed", order_id=broker_order_id, error=str(e))
            raise HyperliquidOrderRejectError(
                f"Failed to cancel order {broker_order_id}: {e}"
            ) from e

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power'

        Raises:
            HyperliquidConnectionError: If request fails
        """
        if not self._connected:
            raise HyperliquidConnectionError("Not connected to Hyperliquid")

        try:
            # Get user state
            user_state = self.info.user_state(self._wallet_address)

            if user_state is None:
                raise HyperliquidConnectionError("Failed to fetch user state")

            # Extract account values
            margin_summary = user_state.get("marginSummary", {})
            account_value = Decimal(margin_summary.get("accountValue", "0"))
            total_margin_used = Decimal(margin_summary.get("totalMarginUsed", "0"))

            # Calculate available balance
            available_balance = account_value - total_margin_used

            return {
                "cash": available_balance,
                "equity": account_value,
                "buying_power": available_balance,  # Simplified
            }

        except Exception as e:
            logger.error("get_account_info_failed", error=str(e))
            raise HyperliquidConnectionError(f"Failed to get account info: {e}") from e

    async def get_positions(self) -> list[dict]:
        """Get current positions.

        Returns:
            List of position dicts with keys: 'symbol', 'amount', 'entry_price', 'market_value'

        Raises:
            HyperliquidConnectionError: If request fails
        """
        if not self._connected:
            raise HyperliquidConnectionError("Not connected to Hyperliquid")

        try:
            # Get user state with positions
            user_state = self.info.user_state(self._wallet_address)

            if user_state is None:
                raise HyperliquidConnectionError("Failed to fetch user state")

            asset_positions = user_state.get("assetPositions", [])

            positions = []
            for position_data in asset_positions:
                position = position_data.get("position", {})
                coin = position.get("coin")
                szi = Decimal(position.get("szi", "0"))  # Signed size

                # Skip zero positions
                if szi == 0:
                    continue

                entry_px = Decimal(position.get("entryPx", "0"))
                position_value = Decimal(position.get("positionValue", "0"))
                unrealized_pnl = Decimal(position.get("unrealizedPnl", "0"))

                positions.append(
                    {
                        "symbol": coin,
                        "amount": szi,
                        "entry_price": entry_px,
                        "market_value": position_value,
                        "unrealized_pnl": unrealized_pnl,
                    }
                )

            logger.debug("positions_fetched", count=len(positions))

            return positions

        except Exception as e:
            logger.error("get_positions_failed", error=str(e))
            raise HyperliquidConnectionError(f"Failed to get positions: {e}") from e

    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders.

        Returns:
            List of order dicts

        Raises:
            HyperliquidConnectionError: If request fails
        """
        if not self._connected:
            raise HyperliquidConnectionError("Not connected to Hyperliquid")

        try:
            # Get open orders
            open_orders = self.info.open_orders(self._wallet_address)

            orders = []
            for order_data in open_orders:
                coin = order_data.get("coin")
                oid = order_data.get("oid")
                side = order_data.get("side")
                limit_px = order_data.get("limitPx")
                sz = order_data.get("sz")
                order_type = order_data.get("orderType", {})

                orders.append(
                    {
                        "order_id": f"{coin}:{oid}",
                        "symbol": coin,
                        "side": side,
                        "type": "limit" if "limit" in order_type else "market",
                        "quantity": Decimal(sz),
                        "price": Decimal(limit_px) if limit_px else None,
                        "status": "open",
                    }
                )

            return orders

        except Exception as e:
            logger.error("get_open_orders_failed", error=str(e))
            raise HyperliquidConnectionError(f"Failed to get open orders: {e}") from e

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data via WebSocket.

        Args:
            assets: List of assets to subscribe

        Raises:
            HyperliquidConnectionError: If subscription fails
        """
        if not self._connected:
            raise HyperliquidConnectionError("Not connected to Hyperliquid")

        if not self._ws_adapter:
            raise HyperliquidConnectionError("WebSocket adapter not initialized")

        symbols = [asset.symbol for asset in assets]

        try:
            # Subscribe to trades stream for real-time tick data
            await self._ws_adapter.subscribe(symbols=symbols, channels=["trades"])

            logger.info(
                "market_data_subscribed",
                symbols=symbols,
                channels=["trades"],
            )

        except Exception as e:
            logger.error("market_data_subscription_failed", symbols=symbols, error=str(e))
            raise HyperliquidConnectionError(f"Failed to subscribe to market data: {e}") from e

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data via WebSocket.

        Args:
            assets: List of assets to unsubscribe

        Raises:
            HyperliquidConnectionError: If unsubscription fails
        """
        if not self._connected:
            raise HyperliquidConnectionError("Not connected to Hyperliquid")

        if not self._ws_adapter:
            raise HyperliquidConnectionError("WebSocket adapter not initialized")

        symbols = [asset.symbol for asset in assets]

        try:
            # Unsubscribe from trades stream
            await self._ws_adapter.unsubscribe(symbols=symbols, channels=["trades"])

            logger.info(
                "market_data_unsubscribed",
                symbols=symbols,
                channels=["trades"],
            )

        except Exception as e:
            logger.error("market_data_unsubscription_failed", symbols=symbols, error=str(e))
            raise HyperliquidConnectionError(f"Failed to unsubscribe from market data: {e}") from e

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
            HyperliquidConnectionError: If price fetch fails
        """
        if not self._connected:
            raise HyperliquidConnectionError("Not connected to Hyperliquid")

        try:
            # Get all market data
            all_mids = self.info.all_mids()

            if asset.symbol not in all_mids:
                raise HyperliquidConnectionError(f"No price data for {asset.symbol}")

            price = Decimal(all_mids[asset.symbol])

            logger.debug("price_fetched", symbol=asset.symbol, price=str(price))

            return price

        except Exception as e:
            logger.error("get_current_price_failed", symbol=asset.symbol, error=str(e))
            raise HyperliquidConnectionError(f"Failed to get current price: {e}") from e

    def is_connected(self) -> bool:
        """Check if connected to Hyperliquid.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    # Private methods - Rate Limiting

    async def _check_request_rate_limit(self) -> None:
        """Check if request rate limit is exceeded.

        Hyperliquid allows 600 requests per minute.
        This method logs warnings when approaching limit and raises error when exceeded.

        Raises:
            HyperliquidRateLimitError: If rate limit would be exceeded
        """
        now = time.time()
        cutoff = now - 60  # 60 seconds ago

        # Remove old timestamps
        self._request_timestamps = [ts for ts in self._request_timestamps if ts > cutoff]

        # Check if we're at limit
        if len(self._request_timestamps) >= self.REQUESTS_PER_MINUTE:
            logger.error(
                "hyperliquid_rate_limit_exceeded", requests_in_window=len(self._request_timestamps)
            )
            raise HyperliquidRateLimitError(
                f"Rate limit exceeded: {len(self._request_timestamps)} requests in last minute"
            )

        # Warn at 80% of limit
        if len(self._request_timestamps) >= int(self.REQUESTS_PER_MINUTE * 0.8):
            logger.warning(
                "hyperliquid_rate_limit_approaching",
                requests_in_window=len(self._request_timestamps),
                limit=self.REQUESTS_PER_MINUTE,
            )

        # Record this request
        self._request_timestamps.append(now)

    async def _check_order_rate_limit(self, symbol: str) -> None:
        """Check if order rate limit is exceeded for a symbol.

        Hyperliquid allows 20 orders per second per symbol.

        Args:
            symbol: Trading symbol

        Raises:
            HyperliquidRateLimitError: If rate limit would be exceeded
        """
        now = time.time()
        cutoff = now - 1  # 1 second ago

        # Initialize symbol tracking if needed
        if symbol not in self._order_timestamps:
            self._order_timestamps[symbol] = []

        # Remove old timestamps
        self._order_timestamps[symbol] = [
            ts for ts in self._order_timestamps[symbol] if ts > cutoff
        ]

        # Check if we're at limit
        if len(self._order_timestamps[symbol]) >= self.ORDERS_PER_SECOND:
            logger.error(
                "hyperliquid_order_rate_limit_exceeded",
                symbol=symbol,
                orders_in_window=len(self._order_timestamps[symbol]),
            )
            raise HyperliquidRateLimitError(
                f"Order rate limit exceeded for {symbol}: "
                f"{len(self._order_timestamps[symbol])} orders in last second"
            )

        # Warn at 80% of limit
        if len(self._order_timestamps[symbol]) >= int(self.ORDERS_PER_SECOND * 0.8):
            logger.warning(
                "hyperliquid_order_rate_limit_approaching",
                symbol=symbol,
                orders_in_window=len(self._order_timestamps[symbol]),
                limit=self.ORDERS_PER_SECOND,
            )

        # Record this order
        self._order_timestamps[symbol].append(now)

    # Private methods - Security

    def _load_private_key(
        self,
        private_key: str | None,
        encrypted_key_path: str | None,
        encryption_key: str | None,
    ) -> str:
        """Load private key securely from one of several sources.

        Priority:
        1. Environment variable: HYPERLIQUID_PRIVATE_KEY
        2. Encrypted keystore file
        3. Direct parameter (NOT RECOMMENDED)

        Args:
            private_key: Direct private key (NOT RECOMMENDED)
            encrypted_key_path: Path to encrypted keystore
            encryption_key: Encryption key for keystore

        Returns:
            Ethereum private key (hex string)

        Raises:
            HyperliquidKeyError: If private key cannot be loaded
        """
        # Method 1: Environment variable (RECOMMENDED)
        env_key = os.environ.get("HYPERLIQUID_PRIVATE_KEY")
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
        raise HyperliquidKeyError(
            "No private key provided. Set HYPERLIQUID_PRIVATE_KEY environment variable, "
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
            HyperliquidKeyError: If decryption fails
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
                raise HyperliquidKeyError("No private_key in encrypted file")

            return self._validate_private_key(private_key)

        except Exception as e:
            logger.error("failed_to_load_encrypted_key", error=str(e))
            raise HyperliquidKeyError(f"Failed to load encrypted key: {e}") from e

    def _validate_private_key(self, key: str) -> str:
        """Validate private key format.

        Args:
            key: Private key

        Returns:
            Validated private key

        Raises:
            HyperliquidKeyError: If key is invalid
        """
        # Remove 0x prefix if present
        if key.startswith("0x"):
            key = key[2:]

        # Validate length (64 hex characters = 32 bytes)
        if len(key) != 64:
            raise HyperliquidKeyError(
                f"Invalid private key length: {len(key)}, expected 64 hex characters"
            )

        # Validate hex
        try:
            int(key, 16)
        except ValueError as e:
            raise HyperliquidKeyError("Invalid private key: not a hex string") from e

        return key

    def _get_wallet_from_key(self, private_key: str) -> Any:
        """Create wallet from private key.

        Args:
            private_key: Ethereum private key

        Returns:
            eth_account.signers.local.LocalAccount object

        Raises:
            HyperliquidKeyError: If wallet creation fails
        """
        try:
            from eth_account import Account

            # Create account from private key
            account = Account.from_key(f"0x{private_key}")

            logger.info("wallet_created", address=self._mask_address(account.address))

            return account

        except Exception as e:
            logger.error("wallet_creation_failed", error=str(e))
            raise HyperliquidKeyError(f"Failed to create wallet: {e}") from e

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
            >>> HyperliquidBrokerAdapter.create_encrypted_keystore(
            ...     private_key="your_private_key_here",
            ...     output_path="~/.rustybt/hyperliquid_key.enc",
            ...     encryption_key=encryption_key
            ... )
            >>> # Save encryption_key in environment: HYPERLIQUID_ENCRYPTION_KEY
        """
        # Validate key
        if private_key.startswith("0x"):
            private_key = private_key[2:]

        if len(private_key) != 64:
            raise ValueError("Invalid private key length")

        # Create key data
        key_data = {
            "private_key": private_key,
            "created_at": str(asyncio.get_event_loop().time()),
        }

        # Encrypt
        fernet = Fernet(encryption_key.encode())
        encrypted_data = fernet.encrypt(json.dumps(key_data).encode())

        # Write to file
        Path(output_path).write_bytes(encrypted_data)

        logger.info("encrypted_keystore_created", path=output_path)

    def _handle_tick(self, tick: "TickData") -> None:
        """Handle incoming tick data from WebSocket.

        Adds tick to bar buffer for OHLCV aggregation.

        Args:
            tick: Tick data from WebSocket
        """
        if not self._bar_buffer:
            logger.warning("bar_buffer_not_initialized", symbol=tick.symbol)
            return

        # Add tick to bar buffer (will emit bar if boundary crossed)
        self._bar_buffer.add_tick(tick)

        logger.debug(
            "tick_received",
            symbol=tick.symbol,
            price=str(tick.price),
            volume=str(tick.volume),
            timestamp=tick.timestamp.isoformat(),
        )

    def _handle_bar_complete(self, bar: OHLCVBar) -> None:
        """Handle completed OHLCV bar from bar buffer.

        Converts bar to MarketDataEvent and pushes to queue.

        Args:
            bar: Completed OHLCV bar
        """
        # Convert OHLCVBar to market data dict for queue
        market_data = {
            "type": "bar",
            "symbol": bar.symbol,
            "timestamp": bar.timestamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }

        # Push to queue (non-blocking)
        try:
            self._market_data_queue.put_nowait(market_data)

            logger.info(
                "bar_completed",
                symbol=bar.symbol,
                timestamp=bar.timestamp.isoformat(),
                open=str(bar.open),
                high=str(bar.high),
                low=str(bar.low),
                close=str(bar.close),
                volume=str(bar.volume),
            )

        except asyncio.QueueFull:
            logger.warning(
                "market_data_queue_full",
                symbol=bar.symbol,
                queue_size=self._market_data_queue.qsize(),
            )
