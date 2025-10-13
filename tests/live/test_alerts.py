"""Unit tests for alert system.

Tests AlertManager with different alert channels:
- Email alerts
- SMS alerts (Twilio)
- Webhook alerts
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rustybt.live.alerts import AlertConfig, AlertManager, AlertPayload


class TestAlertConfig:
    """Tests for AlertConfig."""

    def test_initialization_minimal(self) -> None:
        """Test minimal config initialization."""
        config = AlertConfig()
        assert not config.smtp_enabled
        assert not config.sms_enabled
        assert not config.webhook_enabled

    def test_initialization_smtp(self) -> None:
        """Test SMTP config initialization."""
        config = AlertConfig(
            smtp_enabled=True,
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="test@example.com",
            smtp_password="password",
            smtp_from="alerts@example.com",
            smtp_to=["recipient@example.com"],
        )
        assert config.smtp_enabled
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587

    def test_initialization_sms(self) -> None:
        """Test SMS config initialization."""
        config = AlertConfig(
            sms_enabled=True,
            twilio_account_sid="AC123",
            twilio_auth_token="token123",
            twilio_from_number="+15551234567",
            twilio_to_numbers=["+15559876543"],
        )
        assert config.sms_enabled
        assert config.twilio_account_sid == "AC123"

    def test_initialization_webhook(self) -> None:
        """Test webhook config initialization."""
        config = AlertConfig(
            webhook_enabled=True,
            webhook_urls=["https://hooks.example.com/webhook"],
            webhook_hmac_secret="secret123",
        )
        assert config.webhook_enabled
        assert len(config.webhook_urls) == 1

    def test_from_env(self) -> None:
        """Test creating config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.test.com",
                "SMTP_PORT": "587",
                "SMTP_USERNAME": "user@test.com",
                "SMTP_PASSWORD": "pass",
                "ALERT_EMAIL_FROM": "alerts@test.com",
                "ALERT_EMAIL_TO": "recipient1@test.com,recipient2@test.com",
                "ALERT_RATE_LIMIT": "5",
            },
        ):
            config = AlertConfig.from_env()
            assert config.smtp_enabled
            assert config.smtp_host == "smtp.test.com"
            assert config.smtp_port == 587
            assert len(config.smtp_to) == 2
            assert config.rate_limit_alerts_per_hour == 5

    def test_from_env_empty(self) -> None:
        """Test creating config from empty environment."""
        with patch.dict(os.environ, {}, clear=True):
            config = AlertConfig.from_env()
            assert not config.smtp_enabled
            assert not config.sms_enabled
            assert not config.webhook_enabled


class TestAlertPayload:
    """Tests for AlertPayload."""

    def test_initialization(self) -> None:
        """Test payload initialization."""
        payload = AlertPayload(
            event_type="circuit_breaker_tripped",
            strategy_name="TestStrategy",
            circuit_breaker_type="drawdown",
            reason="Portfolio drawdown exceeded -10%",
            details={"drawdown": "-0.11", "threshold": "-0.10"},
            timestamp="2025-10-03T10:30:00",
        )
        assert payload.event_type == "circuit_breaker_tripped"
        assert payload.strategy_name == "TestStrategy"
        assert payload.circuit_breaker_type == "drawdown"
        assert "drawdown" in payload.details

    def test_model_dump(self) -> None:
        """Test payload can be serialized."""
        payload = AlertPayload(
            event_type="test",
            strategy_name="Test",
            circuit_breaker_type="manual",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )
        data = payload.model_dump()
        assert data["event_type"] == "test"
        assert data["strategy_name"] == "Test"


class TestAlertManager:
    """Tests for AlertManager."""

    def test_initialization(self) -> None:
        """Test manager initializes correctly."""
        config = AlertConfig()
        manager = AlertManager(config, "TestStrategy")
        assert manager._strategy_name == "TestStrategy"

    def test_rate_limiting(self) -> None:
        """Test alert rate limiting works."""
        config = AlertConfig(rate_limit_alerts_per_hour=2)
        manager = AlertManager(config, "TestStrategy")

        # First two alerts should pass rate limit
        assert manager._check_rate_limit("drawdown")
        assert manager._check_rate_limit("drawdown")

        # Third alert should be blocked
        assert not manager._check_rate_limit("drawdown")

    def test_rate_limiting_per_breaker(self) -> None:
        """Test rate limiting is per breaker type."""
        config = AlertConfig(rate_limit_alerts_per_hour=2)
        manager = AlertManager(config, "TestStrategy")

        # Two drawdown alerts
        assert manager._check_rate_limit("drawdown")
        assert manager._check_rate_limit("drawdown")

        # Daily loss alerts should still work
        assert manager._check_rate_limit("daily_loss")
        assert manager._check_rate_limit("daily_loss")

    @pytest.mark.asyncio
    async def test_send_alert_no_channels(self) -> None:
        """Test send_alert with no channels configured."""
        config = AlertConfig()
        manager = AlertManager(config, "TestStrategy")

        statuses = await manager.send_alert(
            event_type="circuit_breaker_tripped",
            circuit_breaker_type="drawdown",
            reason="Test",
        )
        assert len(statuses) == 0

    @pytest.mark.asyncio
    async def test_send_alert_rate_limited(self) -> None:
        """Test send_alert respects rate limiting."""
        config = AlertConfig(
            smtp_enabled=True,
            smtp_host="smtp.test.com",
            smtp_to=["test@example.com"],
            rate_limit_alerts_per_hour=1,
        )
        manager = AlertManager(config, "TestStrategy")

        # Mock SMTP
        with patch.object(manager, "_send_email", new_callable=AsyncMock) as mock_email:
            # First alert should send
            await manager.send_alert(
                event_type="circuit_breaker_tripped",
                circuit_breaker_type="drawdown",
                reason="Test1",
            )
            assert mock_email.called

            # Second alert should be rate limited
            mock_email.reset_mock()
            await manager.send_alert(
                event_type="circuit_breaker_tripped",
                circuit_breaker_type="drawdown",
                reason="Test2",
            )
            assert not mock_email.called

    @pytest.mark.asyncio
    async def test_send_email_success(self) -> None:
        """Test email sending succeeds."""
        config = AlertConfig(
            smtp_enabled=True,
            smtp_host="smtp.test.com",
            smtp_username="user@test.com",
            smtp_password="pass",
            smtp_from="alerts@test.com",
            smtp_to=["recipient@test.com"],
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="circuit_breaker_tripped",
            strategy_name="TestStrategy",
            circuit_breaker_type="drawdown",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        # Mock SMTP
        with patch.object(manager, "_send_smtp_sync") as mock_smtp:
            status = await manager._send_email(payload)
            assert status.success
            assert status.channel == "email"
            assert mock_smtp.called

    @pytest.mark.asyncio
    async def test_send_email_failure(self) -> None:
        """Test email sending handles failures."""
        config = AlertConfig(
            smtp_enabled=True,
            smtp_host="smtp.test.com",
            smtp_to=["recipient@test.com"],
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="test",
            strategy_name="Test",
            circuit_breaker_type="test",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        # Mock SMTP to raise exception
        with patch.object(manager, "_send_smtp_sync", side_effect=Exception("SMTP error")):
            status = await manager._send_email(payload)
            assert not status.success
            assert status.channel == "email"
            assert "SMTP error" in status.error

    @pytest.mark.asyncio
    async def test_send_sms_success(self) -> None:
        """Test SMS sending succeeds."""
        config = AlertConfig(
            sms_enabled=True,
            twilio_account_sid="AC123",
            twilio_auth_token="token123",
            twilio_from_number="+15551234567",
            twilio_to_numbers=["+15559876543"],
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="circuit_breaker_tripped",
            strategy_name="TestStrategy",
            circuit_breaker_type="drawdown",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        # Mock aiohttp session
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_post_context = AsyncMock()
            mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_post_context)
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value = mock_session_context

            status = await manager._send_sms(payload)
            assert status.success
            assert status.channel == "sms"

    @pytest.mark.asyncio
    async def test_send_sms_failure(self) -> None:
        """Test SMS sending handles failures."""
        config = AlertConfig(
            sms_enabled=True,
            twilio_account_sid="AC123",
            twilio_auth_token="token123",
            twilio_from_number="+15551234567",
            twilio_to_numbers=["+15559876543"],
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="test",
            strategy_name="Test",
            circuit_breaker_type="test",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        # Mock aiohttp to return error
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad request")
            mock_post_context = AsyncMock()
            mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_post_context)
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value = mock_session_context

            status = await manager._send_sms(payload)
            assert not status.success
            assert status.channel == "sms"

    @pytest.mark.asyncio
    async def test_send_webhook_success(self) -> None:
        """Test webhook sending succeeds."""
        config = AlertConfig(
            webhook_enabled=True,
            webhook_urls=["https://hooks.example.com/webhook"],
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="circuit_breaker_tripped",
            strategy_name="TestStrategy",
            circuit_breaker_type="drawdown",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        # Mock aiohttp session
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post_context = AsyncMock()
            mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_post_context)
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value = mock_session_context

            status = await manager._send_webhook(payload, config.webhook_urls[0])
            assert status.success
            assert "webhook:" in status.channel

    @pytest.mark.asyncio
    async def test_send_webhook_with_auth(self) -> None:
        """Test webhook sending with authentication."""
        url = "https://hooks.example.com/webhook"
        config = AlertConfig(
            webhook_enabled=True,
            webhook_urls=[url],
            webhook_auth_tokens={url: "token123"},
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="test",
            strategy_name="Test",
            circuit_breaker_type="test",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        # Mock aiohttp and verify auth header
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post_context = AsyncMock()
            mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_post_context)
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value = mock_session_context

            await manager._send_webhook(payload, url)

            # Verify Authorization header was added
            call_kwargs = mock_session_instance.post.call_args[1]
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"] == "Bearer token123"

    @pytest.mark.asyncio
    async def test_send_webhook_with_hmac(self) -> None:
        """Test webhook sending with HMAC signature."""
        url = "https://hooks.example.com/webhook"
        config = AlertConfig(
            webhook_enabled=True,
            webhook_urls=[url],
            webhook_hmac_secret="secret123",
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="test",
            strategy_name="Test",
            circuit_breaker_type="test",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        # Mock aiohttp and verify HMAC header
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post_context = AsyncMock()
            mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_post_context)
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value = mock_session_context

            await manager._send_webhook(payload, url)

            # Verify signature header was added
            call_kwargs = mock_session_instance.post.call_args[1]
            assert "X-RustyBT-Signature" in call_kwargs["headers"]

    @pytest.mark.asyncio
    async def test_send_webhook_failure(self) -> None:
        """Test webhook sending handles failures."""
        url = "https://hooks.example.com/webhook"
        config = AlertConfig(
            webhook_enabled=True,
            webhook_urls=[url],
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="test",
            strategy_name="Test",
            circuit_breaker_type="test",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        # Mock aiohttp to return error
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Server error")
            mock_post_context = AsyncMock()
            mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_post_context)
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value = mock_session_context

            status = await manager._send_webhook(payload, url)
            assert not status.success

    @pytest.mark.asyncio
    async def test_send_webhook_invalid_url(self) -> None:
        """Test webhook handles invalid URLs."""
        config = AlertConfig(
            webhook_enabled=True,
            webhook_urls=["invalid-url"],
        )
        manager = AlertManager(config, "TestStrategy")

        payload = AlertPayload(
            event_type="test",
            strategy_name="Test",
            circuit_breaker_type="test",
            reason="Test",
            timestamp="2025-10-03T10:30:00",
        )

        status = await manager._send_webhook(payload, "invalid-url")
        assert not status.success
        assert "Invalid webhook URL" in status.error

    @pytest.mark.asyncio
    async def test_send_alert_multiple_channels(self) -> None:
        """Test sending alerts to multiple channels."""
        config = AlertConfig(
            smtp_enabled=True,
            smtp_host="smtp.test.com",
            smtp_to=["test@example.com"],
            sms_enabled=True,
            twilio_account_sid="AC123",
            twilio_auth_token="token",
            twilio_from_number="+15551234567",
            twilio_to_numbers=["+15559876543"],
            webhook_enabled=True,
            webhook_urls=["https://hooks.example.com/webhook"],
        )
        manager = AlertManager(config, "TestStrategy")

        # Mock all send methods
        with (
            patch.object(manager, "_send_email", new_callable=AsyncMock) as mock_email,
            patch.object(manager, "_send_sms", new_callable=AsyncMock) as mock_sms,
            patch.object(manager, "_send_webhook", new_callable=AsyncMock) as mock_webhook,
        ):
            await manager.send_alert(
                event_type="circuit_breaker_tripped",
                circuit_breaker_type="drawdown",
                reason="Test",
            )

            assert mock_email.called
            assert mock_sms.called
            assert mock_webhook.called
