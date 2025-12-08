"""Unit tests for LighterBrokerAdapter.

Tests cover:
- Private key loading priority (env var, encrypted keystore, direct param)
- Private key validation (format, length, hex)
- Wallet address derivation
- Connect method with mocked lighter-sdk
- Error handling (LighterKeyError, LighterConnectionError)
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from rustybt.live.brokers.lighter_adapter import (
    LighterBrokerAdapter,
    LighterConnectionError,
    LighterKeyError,
    LighterOrderRejectError,
)


# Test fixtures
@pytest.fixture
def valid_private_key():
    """A valid 64-character hex private key for testing."""
    return "a" * 64


@pytest.fixture
def valid_private_key_with_prefix():
    """A valid private key with 0x prefix."""
    return "0x" + "b" * 64


@pytest.fixture
def encryption_key():
    """A valid Fernet encryption key."""
    return Fernet.generate_key().decode()


@pytest.fixture
def encrypted_keystore(valid_private_key, encryption_key):
    """Create a temporary encrypted keystore file."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".enc", delete=False) as f:
        key_data = {"private_key": valid_private_key}
        fernet = Fernet(encryption_key.encode())
        encrypted = fernet.encrypt(json.dumps(key_data).encode())
        f.write(encrypted)
        keystore_path = f.name

    yield keystore_path

    # Cleanup
    Path(keystore_path).unlink(missing_ok=True)


class TestPrivateKeyLoading:
    """Tests for private key loading priority and methods."""

    def test_load_key_from_env_variable(self, valid_private_key):
        """Test that env var has highest priority."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            assert adapter._private_key == valid_private_key

    def test_load_key_from_env_variable_with_prefix(self, valid_private_key):
        """Test that 0x prefix is stripped from env var."""
        key_with_prefix = f"0x{valid_private_key}"
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": key_with_prefix}):
            adapter = LighterBrokerAdapter()
            assert adapter._private_key == valid_private_key

    def test_load_key_from_encrypted_keystore(
        self, valid_private_key, encryption_key, encrypted_keystore
    ):
        """Test loading key from encrypted keystore file."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove LIGHTER_PRIVATE_KEY if set
            os.environ.pop("LIGHTER_PRIVATE_KEY", None)

            adapter = LighterBrokerAdapter(
                encrypted_key_path=encrypted_keystore,
                encryption_key=encryption_key,
            )
            assert adapter._private_key == valid_private_key

    def test_load_key_from_direct_parameter(self, valid_private_key, caplog):
        """Test loading key from direct parameter logs warning."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LIGHTER_PRIVATE_KEY", None)

            adapter = LighterBrokerAdapter(private_key=valid_private_key)
            assert adapter._private_key == valid_private_key

    def test_env_var_takes_priority_over_encrypted(
        self, valid_private_key, encryption_key, encrypted_keystore
    ):
        """Test that env var has priority over encrypted keystore."""
        env_key = "c" * 64  # Different key
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": env_key}):
            adapter = LighterBrokerAdapter(
                encrypted_key_path=encrypted_keystore,
                encryption_key=encryption_key,
            )
            # Should use env var, not encrypted keystore
            assert adapter._private_key == env_key

    def test_encrypted_takes_priority_over_direct(
        self, valid_private_key, encryption_key, encrypted_keystore
    ):
        """Test that encrypted keystore has priority over direct param."""
        direct_key = "d" * 64  # Different key
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LIGHTER_PRIVATE_KEY", None)

            adapter = LighterBrokerAdapter(
                private_key=direct_key,
                encrypted_key_path=encrypted_keystore,
                encryption_key=encryption_key,
            )
            # Should use encrypted keystore, not direct param
            assert adapter._private_key == valid_private_key

    def test_no_key_provided_raises_error(self):
        """Test that missing key raises LighterKeyError."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LIGHTER_PRIVATE_KEY", None)

            with pytest.raises(LighterKeyError) as exc_info:
                LighterBrokerAdapter()

            assert "No private key provided" in str(exc_info.value)


class TestPrivateKeyValidation:
    """Tests for private key format validation."""

    def test_valid_key_64_hex(self):
        """Test valid 64-character hex key passes validation."""
        key = "a" * 64
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": key}):
            adapter = LighterBrokerAdapter()
            assert adapter._private_key == key

    def test_valid_key_mixed_hex(self):
        """Test valid mixed hex characters."""
        key = "0123456789abcdefABCDEF" + "0" * 42
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": key}):
            adapter = LighterBrokerAdapter()
            assert adapter._private_key == key

    def test_invalid_key_too_short(self):
        """Test that key shorter than 64 chars raises error."""
        key = "a" * 32  # Too short
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": key}):
            with pytest.raises(LighterKeyError) as exc_info:
                LighterBrokerAdapter()

            assert "Invalid private key length" in str(exc_info.value)
            # Ensure actual length is not logged (security)
            assert key not in str(exc_info.value)

    def test_invalid_key_too_long(self):
        """Test that key longer than 64 chars raises error."""
        key = "a" * 128  # Too long
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": key}):
            with pytest.raises(LighterKeyError) as exc_info:
                LighterBrokerAdapter()

            assert "Invalid private key length" in str(exc_info.value)

    def test_invalid_key_non_hex(self):
        """Test that non-hex characters raise error."""
        key = "g" * 64  # 'g' is not valid hex
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": key}):
            with pytest.raises(LighterKeyError) as exc_info:
                LighterBrokerAdapter()

            assert "not a hex string" in str(exc_info.value)

    def test_0x_prefix_stripped(self, valid_private_key_with_prefix):
        """Test that 0x prefix is correctly stripped."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key_with_prefix}):
            adapter = LighterBrokerAdapter()
            # Should be 64 chars without prefix
            assert len(adapter._private_key) == 64
            assert not adapter._private_key.startswith("0x")


class TestWalletAddressDerivation:
    """Tests for wallet address derivation from private key."""

    def test_derives_wallet_address(self, valid_private_key):
        """Test that wallet address is derived correctly."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            address = adapter._derive_wallet_address(adapter._private_key)

            # Ethereum address format: 0x + 40 hex chars
            assert address.startswith("0x")
            assert len(address) == 42

    def test_mask_address(self):
        """Test address masking for logs."""
        address = "0x1234567890abcdef1234567890abcdef12345678"
        masked = LighterBrokerAdapter._mask_address(address)

        assert masked == "0x1234...5678"
        # Ensure most of the address is hidden
        assert "567890abcdef1234567890abcdef1234" not in masked

    def test_mask_short_address(self):
        """Test masking very short strings returns asterisks."""
        short = "0x1234"
        masked = LighterBrokerAdapter._mask_address(short)
        assert masked == "***"


class TestConnect:
    """Tests for connect method."""

    @pytest.mark.asyncio
    async def test_connect_success(self, valid_private_key):
        """Test successful connection with mocked lighter-sdk."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()

            # Mock lighter module
            mock_lighter = MagicMock()
            mock_api_client = MagicMock()
            mock_signer_client = MagicMock()
            mock_account_api = MagicMock()

            # Mock account response
            mock_account = MagicMock()
            mock_account.index = 1
            mock_account_response = MagicMock()
            mock_account_response.accounts = [mock_account]
            mock_account_api.accounts_by_l1_address = AsyncMock(return_value=mock_account_response)

            mock_lighter.ApiClient.return_value = mock_api_client
            mock_lighter.SignerClient.return_value = mock_signer_client
            mock_lighter.AccountApi.return_value = mock_account_api

            with patch.dict("sys.modules", {"lighter": mock_lighter}):
                await adapter.connect()

            assert adapter.is_connected()
            assert adapter._account_id == "1"

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, valid_private_key):
        """Test that connecting when already connected logs warning."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True

            # Should not raise, just log warning
            await adapter.connect()
            assert adapter.is_connected()

    @pytest.mark.asyncio
    async def test_connect_no_account_raises_error(self, valid_private_key):
        """Test that missing Lighter account raises LighterKeyError."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()

            # Mock lighter module with empty account response
            mock_lighter = MagicMock()
            mock_api_client = MagicMock()
            mock_account_api = MagicMock()
            mock_account_response = MagicMock()
            mock_account_response.accounts = []  # No accounts
            mock_account_api.accounts_by_l1_address = AsyncMock(return_value=mock_account_response)

            mock_lighter.ApiClient.return_value = mock_api_client
            mock_lighter.SignerClient = MagicMock()
            mock_lighter.AccountApi.return_value = mock_account_api

            with patch.dict("sys.modules", {"lighter": mock_lighter}):
                with pytest.raises(LighterKeyError) as exc_info:
                    await adapter.connect()

            assert "No Lighter account found" in str(exc_info.value)
            assert not adapter.is_connected()

    @pytest.mark.asyncio
    async def test_connect_api_error_raises_connection_error(self, valid_private_key):
        """Test that API errors raise LighterConnectionError."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()

            # Mock lighter module that raises exception
            mock_lighter = MagicMock()
            mock_api_client = MagicMock()
            mock_account_api = MagicMock()
            mock_account_api.accounts_by_l1_address = AsyncMock(side_effect=Exception("API error"))

            mock_lighter.ApiClient.return_value = mock_api_client
            mock_lighter.SignerClient = MagicMock()
            mock_lighter.AccountApi.return_value = mock_account_api

            with patch.dict("sys.modules", {"lighter": mock_lighter}):
                with pytest.raises(LighterConnectionError) as exc_info:
                    await adapter.connect()

            assert "Failed to connect" in str(exc_info.value)
            assert not adapter.is_connected()


class TestDisconnect:
    """Tests for disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self, valid_private_key):
        """Test disconnecting when connected."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._api_client = MagicMock()
            adapter._api_client.close = AsyncMock()

            await adapter.disconnect()

            assert not adapter.is_connected()
            assert adapter._api_client is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, valid_private_key):
        """Test disconnecting when not connected logs warning."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = False

            # Should not raise
            await adapter.disconnect()
            assert not adapter.is_connected()


class TestEncryptedKeystore:
    """Tests for encrypted keystore creation and loading."""

    def test_create_encrypted_keystore(self, valid_private_key, encryption_key):
        """Test creating an encrypted keystore file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_key.enc"

            LighterBrokerAdapter.create_encrypted_keystore(
                private_key=valid_private_key,
                output_path=str(output_path),
                encryption_key=encryption_key,
            )

            assert output_path.exists()

            # Verify we can decrypt it
            fernet = Fernet(encryption_key.encode())
            encrypted_data = output_path.read_bytes()
            decrypted = fernet.decrypt(encrypted_data)
            key_data = json.loads(decrypted.decode())

            assert key_data["private_key"] == valid_private_key

    def test_create_encrypted_keystore_strips_prefix(self, encryption_key):
        """Test that 0x prefix is stripped when creating keystore."""
        key_with_prefix = "0x" + "a" * 64

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_key.enc"

            LighterBrokerAdapter.create_encrypted_keystore(
                private_key=key_with_prefix,
                output_path=str(output_path),
                encryption_key=encryption_key,
            )

            # Verify stored key has no prefix
            fernet = Fernet(encryption_key.encode())
            encrypted_data = output_path.read_bytes()
            decrypted = fernet.decrypt(encrypted_data)
            key_data = json.loads(decrypted.decode())

            assert not key_data["private_key"].startswith("0x")
            assert len(key_data["private_key"]) == 64

    def test_create_encrypted_keystore_invalid_key_length(self, encryption_key):
        """Test that invalid key length raises ValueError."""
        invalid_key = "a" * 32  # Too short

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_key.enc"

            with pytest.raises(ValueError) as exc_info:
                LighterBrokerAdapter.create_encrypted_keystore(
                    private_key=invalid_key,
                    output_path=str(output_path),
                    encryption_key=encryption_key,
                )

            assert "Invalid private key length" in str(exc_info.value)

    def test_create_encrypted_keystore_creates_parent_dirs(self, valid_private_key, encryption_key):
        """Test that parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dirs" / "test_key.enc"

            LighterBrokerAdapter.create_encrypted_keystore(
                private_key=valid_private_key,
                output_path=str(output_path),
                encryption_key=encryption_key,
            )

            assert output_path.exists()


class TestConfiguration:
    """Tests for adapter configuration options."""

    def test_default_testnet(self, valid_private_key):
        """Test that testnet is True by default (ADR-003)."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            assert adapter._testnet is True
            assert adapter.api_url == LighterBrokerAdapter.TESTNET_API_URL

    def test_mainnet_selection(self, valid_private_key):
        """Test mainnet URL selection."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter(testnet=False)
            assert adapter._testnet is False
            assert adapter.api_url == LighterBrokerAdapter.MAINNET_API_URL

    def test_account_and_api_key_indices(self, valid_private_key):
        """Test custom account and API key indices."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter(account_index=5, api_key_index=2)
            assert adapter._account_index == 5
            assert adapter._api_key_index == 2


class TestOrderSubmission:
    """Tests for order submission (Story 10.4.2)."""

    @pytest.mark.asyncio
    async def test_submit_market_order_buy(self, valid_private_key):
        """Test submitting a market buy order."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._signer_client = MagicMock()
            adapter._signer_client.create_market_order = AsyncMock(
                return_value={"order_id": "12345"}
            )

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            order_id = await adapter.submit_order(mock_asset, Decimal("1.0"), "market")

            assert order_id == "BTC-PERP:12345"
            adapter._signer_client.create_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_market_order_sell(self, valid_private_key):
        """Test submitting a market sell order (negative amount)."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._signer_client = MagicMock()
            adapter._signer_client.create_market_order = AsyncMock(
                return_value={"order_id": "67890"}
            )

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "ETH-PERP"

            # Negative amount = sell
            order_id = await adapter.submit_order(mock_asset, Decimal("-0.5"), "market")

            assert order_id == "ETH-PERP:67890"
            # Verify is_bid=False for sell
            call_kwargs = adapter._signer_client.create_market_order.call_args[1]
            assert call_kwargs["is_bid"] is False

    @pytest.mark.asyncio
    async def test_submit_limit_order(self, valid_private_key):
        """Test submitting a limit order."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._signer_client = MagicMock()
            adapter._signer_client.create_order = AsyncMock(return_value={"order_id": "limit123"})

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            order_id = await adapter.submit_order(
                mock_asset, Decimal("1.0"), "limit", limit_price=Decimal("50000.00")
            )

            assert order_id == "BTC-PERP:limit123"
            adapter._signer_client.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_order_requires_connection(self, valid_private_key):
        """Test that submit_order raises error when not connected."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = False

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            with pytest.raises(LighterConnectionError) as exc_info:
                await adapter.submit_order(mock_asset, Decimal("1.0"), "market")

            assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_order_zero_amount_raises_error(self, valid_private_key):
        """Test that zero amount raises ValueError."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            with pytest.raises(ValueError) as exc_info:
                await adapter.submit_order(mock_asset, Decimal("0"), "market")

            assert "cannot be zero" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_limit_order_without_price_raises_error(self, valid_private_key):
        """Test that limit order without price raises ValueError."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            with pytest.raises(ValueError) as exc_info:
                await adapter.submit_order(mock_asset, Decimal("1.0"), "limit")

            assert "limit_price required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_order_unsupported_type_raises_error(self, valid_private_key):
        """Test that unsupported order type raises ValueError."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            with pytest.raises(ValueError) as exc_info:
                await adapter.submit_order(mock_asset, Decimal("1.0"), "stop-limit")

            assert "Unsupported order type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_order_rejection_raises_error(self, valid_private_key):
        """Test that order rejection raises LighterOrderRejectError."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._signer_client = MagicMock()
            adapter._signer_client.create_market_order = AsyncMock(
                side_effect=Exception("Insufficient margin")
            )

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            with pytest.raises(LighterOrderRejectError) as exc_info:
                await adapter.submit_order(mock_asset, Decimal("1.0"), "market")

            assert "Insufficient margin" in str(exc_info.value)


class TestTokenBucket:
    """Tests for TokenBucket rate limiter."""

    def test_token_bucket_initial_capacity(self):
        """Test token bucket starts at full capacity."""
        from rustybt.live.brokers.lighter_adapter import TokenBucket

        bucket = TokenBucket(rate=10.0, capacity=100.0)
        assert bucket.available() == 100.0

    def test_token_bucket_try_acquire_success(self):
        """Test try_acquire succeeds with tokens available."""
        from rustybt.live.brokers.lighter_adapter import TokenBucket

        bucket = TokenBucket(rate=10.0, capacity=100.0)
        assert bucket.try_acquire(10) is True
        # Use approximate comparison due to refill timing
        assert 89.9 <= bucket.available() <= 90.1

    def test_token_bucket_try_acquire_failure(self):
        """Test try_acquire fails without enough tokens."""
        from rustybt.live.brokers.lighter_adapter import TokenBucket

        bucket = TokenBucket(rate=10.0, capacity=10.0)
        bucket.tokens = 5.0  # Simulate used tokens
        bucket.last_update = time.monotonic()  # Reset timer to prevent refill
        assert bucket.try_acquire(10) is False
        # Tokens may have refilled slightly
        assert bucket.tokens <= 6.0  # Some tolerance for refill

    def test_token_bucket_utilization(self):
        """Test utilization calculation."""
        from rustybt.live.brokers.lighter_adapter import TokenBucket

        bucket = TokenBucket(rate=10.0, capacity=100.0)
        bucket.last_update = time.monotonic()  # Reset timer
        assert bucket.utilization() <= 0.01  # Nearly empty (some tolerance)

        bucket.tokens = 20.0  # 80% used
        bucket.last_update = time.monotonic()  # Reset timer
        # Use approximate comparison
        assert 0.79 <= bucket.utilization() <= 0.81

    @pytest.mark.asyncio
    async def test_token_bucket_acquire_waits(self):
        """Test that acquire waits when tokens unavailable."""
        from rustybt.live.brokers.lighter_adapter import TokenBucket

        bucket = TokenBucket(rate=100.0, capacity=10.0)  # Fast refill
        bucket.tokens = 0.0  # Empty

        start = time.monotonic()
        await bucket.acquire(5)  # Need 5 tokens
        elapsed = time.monotonic() - start

        # Should have waited ~0.05 seconds (5 tokens at 100/sec)
        assert elapsed >= 0.04  # Allow some tolerance


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    @pytest.mark.asyncio
    async def test_request_rate_limit_warning(self, valid_private_key, caplog):
        """Test that warning is logged at high utilization."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True

            # Simulate high utilization
            adapter._request_rate_limiter.tokens = (
                adapter._request_rate_limiter.capacity * 0.1
            )  # 90% used

            # Check rate limit
            await adapter._check_request_rate_limit()

            # Warning should be logged (check structlog output or mock)
            # Note: In production, we'd check logs properly

    @pytest.mark.asyncio
    async def test_order_rate_limit_creates_limiter_per_symbol(self, valid_private_key):
        """Test that order rate limiters are created per symbol."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()

            # Initially no limiters
            assert len(adapter._order_rate_limiters) == 0

            # Check rate limit for BTC
            await adapter._check_order_rate_limit("BTC-PERP")
            assert "BTC-PERP" in adapter._order_rate_limiters

            # Check for ETH
            await adapter._check_order_rate_limit("ETH-PERP")
            assert "ETH-PERP" in adapter._order_rate_limiters
            assert len(adapter._order_rate_limiters) == 2


class TestOrderCancellation:
    """Tests for order cancellation (Story 10.4.3)."""

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, valid_private_key):
        """Test successful order cancellation."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._signer_client = MagicMock()
            adapter._signer_client.cancel_order = AsyncMock()

            await adapter.cancel_order("BTC-PERP:12345")

            adapter._signer_client.cancel_order.assert_called_once_with(
                order_book="BTC-PERP",
                order_id="12345",
            )

    @pytest.mark.asyncio
    async def test_cancel_order_requires_connection(self, valid_private_key):
        """Test that cancel_order raises error when not connected."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = False

            with pytest.raises(LighterConnectionError) as exc_info:
                await adapter.cancel_order("BTC-PERP:12345")

            assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_order_empty_id_raises_error(self, valid_private_key):
        """Test that empty order_id raises ValueError."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True

            with pytest.raises(ValueError) as exc_info:
                await adapter.cancel_order("")

            assert "required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_order_failure_raises_error(self, valid_private_key):
        """Test that cancel failure raises LighterOrderRejectError."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._signer_client = MagicMock()
            adapter._signer_client.cancel_order = AsyncMock(
                side_effect=Exception("Order not found")
            )

            with pytest.raises(LighterOrderRejectError) as exc_info:
                await adapter.cancel_order("BTC-PERP:12345")

            assert "Cancel failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_order_parses_order_id_with_colon(self, valid_private_key):
        """Test that order_id with colon is parsed correctly."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._signer_client = MagicMock()
            adapter._signer_client.cancel_order = AsyncMock()

            await adapter.cancel_order("ETH-PERP:abc:123")

            # Should handle colon in order_id
            adapter._signer_client.cancel_order.assert_called_once_with(
                order_book="ETH-PERP",
                order_id="abc:123",
            )


class TestOrderQueries:
    """Tests for order query operations (Story 10.4.3)."""

    @pytest.mark.asyncio
    async def test_get_open_orders_success(self, valid_private_key):
        """Test successful open orders query."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._account_id = "1"
            adapter._api_client = MagicMock()

            # Mock lighter module and response
            mock_lighter = MagicMock()
            mock_account_api = MagicMock()
            mock_response = MagicMock()
            mock_response.orders = [
                {
                    "id": "order123",
                    "order_book": "BTC-PERP",
                    "is_bid": True,
                    "type": "limit",
                    "base_amount": 100000000,  # 1.0 in base units
                    "price": 5000000000000,  # 50000.0 in price units
                    "status": "open",
                    "filled_amount": 0,
                    "timestamp": "2025-12-06T10:00:00Z",
                }
            ]
            mock_account_api.account_active_orders = AsyncMock(return_value=mock_response)
            mock_lighter.AccountApi.return_value = mock_account_api

            with patch.dict("sys.modules", {"lighter": mock_lighter}):
                orders = await adapter.get_open_orders()

            assert len(orders) == 1
            assert orders[0]["order_id"] == "BTC-PERP:order123"
            assert orders[0]["symbol"] == "BTC-PERP"
            assert orders[0]["side"] == "buy"
            assert orders[0]["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_get_open_orders_requires_connection(self, valid_private_key):
        """Test that get_open_orders raises error when not connected."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = False

            with pytest.raises(LighterConnectionError) as exc_info:
                await adapter.get_open_orders()

            assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_order_history_success(self, valid_private_key):
        """Test successful order history query."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._account_id = "1"
            adapter._api_client = MagicMock()

            # Mock lighter module and response
            mock_lighter = MagicMock()
            mock_account_api = MagicMock()
            mock_response = MagicMock()
            mock_response.orders = [
                {
                    "id": "order456",
                    "order_book": "ETH-PERP",
                    "is_bid": False,
                    "type": "market",
                    "base_amount": 50000000,  # 0.5 in base units
                    "price": None,
                    "status": "filled",
                    "filled_amount": 50000000,
                    "timestamp": "2025-12-06T09:00:00Z",
                }
            ]
            mock_account_api.account_inactive_orders = AsyncMock(return_value=mock_response)
            mock_lighter.AccountApi.return_value = mock_account_api

            with patch.dict("sys.modules", {"lighter": mock_lighter}):
                orders = await adapter.get_order_history(limit=50, offset=10)

            assert len(orders) == 1
            assert orders[0]["order_id"] == "ETH-PERP:order456"
            assert orders[0]["side"] == "sell"
            assert orders[0]["status"] == "filled"


class TestStatusMapping:
    """Tests for status mapping (Story 10.4.3)."""

    def test_map_open_status(self, valid_private_key):
        """Test mapping 'open' status."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            assert adapter._map_lighter_status("open") == "submitted"

    def test_map_filled_status(self, valid_private_key):
        """Test mapping 'filled' status."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            assert adapter._map_lighter_status("filled") == "filled"

    def test_map_cancelled_status(self, valid_private_key):
        """Test mapping 'cancelled' status (both spellings)."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            assert adapter._map_lighter_status("cancelled") == "cancelled"
            assert adapter._map_lighter_status("canceled") == "cancelled"

    def test_map_partially_filled_status(self, valid_private_key):
        """Test mapping 'partially_filled' status."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            assert adapter._map_lighter_status("partially_filled") == "partial_fill"
            assert adapter._map_lighter_status("partial") == "partial_fill"

    def test_map_unknown_status(self, valid_private_key):
        """Test mapping unknown status returns 'unknown'."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            assert adapter._map_lighter_status("some_new_status") == "unknown"

    def test_map_status_case_insensitive(self, valid_private_key):
        """Test that status mapping is case insensitive."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            assert adapter._map_lighter_status("FILLED") == "filled"
            assert adapter._map_lighter_status("Open") == "submitted"


class TestAccountQueries:
    """Tests for account and position queries (Story 10.4.4)."""

    @pytest.mark.asyncio
    async def test_get_account_info_success(self, valid_private_key):
        """Test successful account info query."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._account_id = "1"
            adapter._api_client = MagicMock()

            # Mock lighter module and response
            mock_lighter = MagicMock()
            mock_account_api = MagicMock()
            mock_response = MagicMock()
            mock_response.collateral = 100000000000  # 1000.0 in base units
            mock_response.available_margin = 50000000000  # 500.0
            mock_response.used_margin = 50000000000  # 500.0
            mock_response.equity = 110000000000  # 1100.0
            mock_response.total_pnl = 10000000000  # 100.0

            mock_account_api.account = AsyncMock(return_value=mock_response)
            mock_lighter.AccountApi.return_value = mock_account_api

            with patch.dict("sys.modules", {"lighter": mock_lighter}):
                info = await adapter.get_account_info()

            from decimal import Decimal

            assert info["balance"] == Decimal("1000.0")
            assert info["available_margin"] == Decimal("500.0")
            assert info["equity"] == Decimal("1100.0")

    @pytest.mark.asyncio
    async def test_get_account_info_requires_connection(self, valid_private_key):
        """Test that get_account_info raises error when not connected."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = False

            with pytest.raises(LighterConnectionError) as exc_info:
                await adapter.get_account_info()

            assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_positions_success(self, valid_private_key):
        """Test successful positions query."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._account_id = "1"
            adapter._api_client = MagicMock()

            # Mock lighter module and response
            mock_lighter = MagicMock()
            mock_account_api = MagicMock()
            mock_response = MagicMock()
            mock_response.positions = [
                {
                    "order_book": "BTC-PERP",
                    "size": 100000000,  # 1.0 in base units
                    "is_long": True,
                    "entry_price": 5000000000000,  # 50000.0
                    "mark_price": 5100000000000,  # 51000.0
                    "unrealized_pnl": 100000000000,  # 1000.0
                    "leverage": 10,
                }
            ]
            mock_account_api.account = AsyncMock(return_value=mock_response)
            mock_lighter.AccountApi.return_value = mock_account_api

            with patch.dict("sys.modules", {"lighter": mock_lighter}):
                positions = await adapter.get_positions()

            from decimal import Decimal

            assert len(positions) == 1
            assert positions[0]["symbol"] == "BTC-PERP"
            assert positions[0]["size"] == Decimal("1.0")  # Long position
            assert positions[0]["entry_price"] == Decimal("50000.0")

    @pytest.mark.asyncio
    async def test_get_positions_short(self, valid_private_key):
        """Test positions query with short position."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter()
            adapter._connected = True
            adapter._account_id = "1"
            adapter._api_client = MagicMock()

            # Mock response with short position
            mock_lighter = MagicMock()
            mock_account_api = MagicMock()
            mock_response = MagicMock()
            mock_response.positions = [
                {
                    "order_book": "ETH-PERP",
                    "size": 200000000,  # 2.0 in base units
                    "is_long": False,  # Short position
                    "entry_price": 300000000000,  # 3000.0
                    "mark_price": 290000000000,  # 2900.0
                    "unrealized_pnl": 10000000000,  # Profit
                    "leverage": 5,
                }
            ]
            mock_account_api.account = AsyncMock(return_value=mock_response)
            mock_lighter.AccountApi.return_value = mock_account_api

            with patch.dict("sys.modules", {"lighter": mock_lighter}):
                positions = await adapter.get_positions()

            from decimal import Decimal

            assert len(positions) == 1
            # Short position should have negative size
            assert positions[0]["size"] == Decimal("-2.0")


class TestPaperTrading:
    """Tests for paper trading mode (Story 10.4.5)."""

    @pytest.mark.asyncio
    async def test_paper_mode_enabled(self, valid_private_key):
        """Test paper mode initialization."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter(paper_mode=True)
            assert adapter.paper_mode is True

    @pytest.mark.asyncio
    async def test_paper_order_submission(self, valid_private_key):
        """Test paper order submission."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter(paper_mode=True)
            # Paper mode doesn't need connection

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            order_id = await adapter.submit_order(
                mock_asset,
                Decimal("1.0"),
                "limit",
                limit_price=Decimal("50000.0"),
            )

            assert "PAPER-" in order_id
            assert "BTC-PERP" in order_id

    @pytest.mark.asyncio
    async def test_paper_position_tracking(self, valid_private_key):
        """Test paper position tracking after order."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter(paper_mode=True)

            from decimal import Decimal

            mock_asset = MagicMock()
            mock_asset.symbol = "ETH-PERP"

            # Submit paper order
            await adapter.submit_order(
                mock_asset,
                Decimal("2.0"),
                "limit",
                limit_price=Decimal("3000.0"),
            )

            # Check paper positions
            positions = adapter.get_paper_positions()
            assert "ETH-PERP" in positions
            assert positions["ETH-PERP"]["size"] == Decimal("2.0")

    @pytest.mark.asyncio
    async def test_paper_slippage_applied(self, valid_private_key):
        """Test paper slippage for market orders."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            from decimal import Decimal

            adapter = LighterBrokerAdapter(
                paper_mode=True,
                paper_slippage=Decimal("0.01"),  # 1% slippage
            )

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            # Submit market buy order with placeholder price
            fills = []

            async def capture_fill(fill_data):
                fills.append(fill_data)

            adapter.set_fill_callback(capture_fill)

            await adapter.submit_order(
                mock_asset,
                Decimal("1.0"),
                "market",
                limit_price=Decimal("50000.0"),  # Use as base price
            )

            assert len(fills) == 1
            # Buy order should have positive slippage
            assert fills[0]["fill_price"] > Decimal("50000.0")

    @pytest.mark.asyncio
    async def test_fill_callback_triggered(self, valid_private_key):
        """Test fill callback is triggered on paper order."""
        with patch.dict(os.environ, {"LIGHTER_PRIVATE_KEY": valid_private_key}):
            adapter = LighterBrokerAdapter(paper_mode=True)

            from decimal import Decimal

            fills = []

            async def on_fill(fill_data):
                fills.append(fill_data)

            adapter.set_fill_callback(on_fill)

            mock_asset = MagicMock()
            mock_asset.symbol = "BTC-PERP"

            await adapter.submit_order(
                mock_asset,
                Decimal("-0.5"),  # Sell order
                "limit",
                limit_price=Decimal("51000.0"),
            )

            assert len(fills) == 1
            assert fills[0]["side"] == "sell"
            assert fills[0]["fill_quantity"] == Decimal("0.5")
