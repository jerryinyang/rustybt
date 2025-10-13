"""Alert system for live trading circuit breaker notifications.

This module implements the AlertManager that sends alerts when circuit breakers trip:
- Email alerts via SMTP
- SMS alerts via Twilio (optional)
- Webhook alerts to custom endpoints

All alert channels support rate limiting to prevent spam.
"""

import asyncio
import hashlib
import hmac
import json
import os
import smtplib
from collections import defaultdict, deque
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from urllib.parse import urlparse

import aiohttp
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class AlertConfig(BaseModel):
    """Configuration for alert system.

    Args:
        smtp_enabled: Enable email alerts
        smtp_host: SMTP server host
        smtp_port: SMTP server port
        smtp_username: SMTP username
        smtp_password: SMTP password
        smtp_from: From email address
        smtp_to: List of recipient email addresses
        sms_enabled: Enable SMS alerts (requires Twilio)
        twilio_account_sid: Twilio account SID
        twilio_auth_token: Twilio auth token
        twilio_from_number: Twilio phone number (sender)
        twilio_to_numbers: List of recipient phone numbers
        webhook_enabled: Enable webhook alerts
        webhook_urls: List of webhook URLs
        webhook_auth_tokens: Optional dict of URL -> bearer token
        webhook_hmac_secret: Optional HMAC secret for webhook signature
        rate_limit_alerts_per_hour: Max alerts per breaker per hour
    """

    smtp_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_to: list[str] = Field(default_factory=list)

    sms_enabled: bool = False
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    twilio_to_numbers: list[str] = Field(default_factory=list)

    webhook_enabled: bool = False
    webhook_urls: list[str] = Field(default_factory=list)
    webhook_auth_tokens: dict[str, str] = Field(default_factory=dict)
    webhook_hmac_secret: str | None = None

    rate_limit_alerts_per_hour: int = 10

    class Config:
        """Pydantic config."""

        frozen = True

    @classmethod
    def from_env(cls) -> "AlertConfig":
        """Create AlertConfig from environment variables.

        Environment variables:
            SMTP_HOST: SMTP server host
            SMTP_PORT: SMTP server port (default: 587)
            SMTP_USERNAME: SMTP username
            SMTP_PASSWORD: SMTP password
            ALERT_EMAIL_FROM: From email address
            ALERT_EMAIL_TO: Comma-separated list of recipient emails
            TWILIO_ACCOUNT_SID: Twilio account SID
            TWILIO_AUTH_TOKEN: Twilio auth token
            TWILIO_FROM_NUMBER: Twilio sender phone number
            ALERT_PHONE_TO: Comma-separated list of recipient phone numbers
            ALERT_WEBHOOK_URLS: Comma-separated list of webhook URLs
            ALERT_WEBHOOK_HMAC_SECRET: HMAC secret for webhook signatures
            ALERT_RATE_LIMIT: Max alerts per hour (default: 10)

        Returns:
            AlertConfig populated from environment
        """
        smtp_enabled = bool(os.getenv("SMTP_HOST"))
        sms_enabled = bool(os.getenv("TWILIO_ACCOUNT_SID"))
        webhook_enabled = bool(os.getenv("ALERT_WEBHOOK_URLS"))

        return cls(
            smtp_enabled=smtp_enabled,
            smtp_host=os.getenv("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            smtp_from=os.getenv("ALERT_EMAIL_FROM"),
            smtp_to=(
                os.getenv("ALERT_EMAIL_TO", "").split(",") if os.getenv("ALERT_EMAIL_TO") else []
            ),
            sms_enabled=sms_enabled,
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
            twilio_from_number=os.getenv("TWILIO_FROM_NUMBER"),
            twilio_to_numbers=(
                os.getenv("ALERT_PHONE_TO", "").split(",") if os.getenv("ALERT_PHONE_TO") else []
            ),
            webhook_enabled=webhook_enabled,
            webhook_urls=(
                os.getenv("ALERT_WEBHOOK_URLS", "").split(",")
                if os.getenv("ALERT_WEBHOOK_URLS")
                else []
            ),
            webhook_hmac_secret=os.getenv("ALERT_WEBHOOK_HMAC_SECRET"),
            rate_limit_alerts_per_hour=int(os.getenv("ALERT_RATE_LIMIT", "10")),
        )


class AlertPayload(BaseModel):
    """Alert payload sent to all alert channels.

    Args:
        event_type: Type of event (circuit_breaker_tripped, manual_halt)
        strategy_name: Name of strategy
        circuit_breaker_type: Type of circuit breaker (drawdown, daily_loss, etc.)
        reason: Human-readable reason
        details: Additional details about the event
        timestamp: When the event occurred
    """

    event_type: str
    strategy_name: str
    circuit_breaker_type: str
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str

    class Config:
        """Pydantic config."""

        frozen = True


class AlertDeliveryStatus(BaseModel):
    """Status of alert delivery attempt.

    Args:
        channel: Alert channel (email, sms, webhook)
        success: Whether delivery succeeded
        error: Error message if delivery failed
        timestamp: When delivery was attempted
    """

    channel: str
    success: bool
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class AlertManager:
    """Manages alert delivery for circuit breaker events.

    Supports multiple alert channels with rate limiting:
    - Email via SMTP
    - SMS via Twilio
    - Webhooks to custom endpoints

    Args:
        config: AlertConfig with channel settings
        strategy_name: Name of strategy (used in alerts)

    Example:
        >>> config = AlertConfig.from_env()
        >>> manager = AlertManager(config, "MyStrategy")
        >>> await manager.send_alert(payload)
    """

    def __init__(self, config: AlertConfig, strategy_name: str) -> None:
        """Initialize alert manager.

        Args:
            config: AlertConfig with channel settings
            strategy_name: Name of strategy (used in alerts)
        """
        self._config = config
        self._strategy_name = strategy_name
        self._alert_history: dict[str, deque[datetime]] = defaultdict(
            lambda: deque()
        )  # breaker_type -> timestamps
        logger.info(
            "alert_manager_initialized",
            strategy=strategy_name,
            smtp_enabled=config.smtp_enabled,
            sms_enabled=config.sms_enabled,
            webhook_enabled=config.webhook_enabled,
        )

    def _check_rate_limit(self, breaker_type: str) -> bool:
        """Check if alert rate limit exceeded for breaker type.

        Args:
            breaker_type: Type of circuit breaker

        Returns:
            True if within rate limit, False if exceeded
        """
        now = datetime.now()
        cutoff = now - timedelta(hours=1)

        # Remove old alerts outside window
        history = self._alert_history[breaker_type]
        while history and history[0] < cutoff:
            history.popleft()

        # Check count
        if len(history) >= self._config.rate_limit_alerts_per_hour:
            logger.warning(
                "alert_rate_limit_exceeded",
                breaker_type=breaker_type,
                count=len(history),
                limit=self._config.rate_limit_alerts_per_hour,
            )
            return False

        # Record alert
        history.append(now)
        return True

    async def send_alert(
        self,
        event_type: str,
        circuit_breaker_type: str,
        reason: str,
        details: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> list[AlertDeliveryStatus]:
        """Send alert to all enabled channels.

        Args:
            event_type: Type of event (circuit_breaker_tripped, manual_halt)
            circuit_breaker_type: Type of circuit breaker
            reason: Human-readable reason
            details: Additional details
            timestamp: Event timestamp (default: now)

        Returns:
            List of AlertDeliveryStatus for each channel
        """
        # Check rate limit
        if not self._check_rate_limit(circuit_breaker_type):
            logger.warning("alert_dropped_rate_limit", breaker_type=circuit_breaker_type)
            return []

        # Create payload
        payload = AlertPayload(
            event_type=event_type,
            strategy_name=self._strategy_name,
            circuit_breaker_type=circuit_breaker_type,
            reason=reason,
            details=details or {},
            timestamp=timestamp or datetime.now().isoformat(),
        )

        # Send to all channels concurrently
        tasks = []
        if self._config.smtp_enabled:
            tasks.append(self._send_email(payload))
        if self._config.sms_enabled:
            tasks.append(self._send_sms(payload))
        if self._config.webhook_enabled:
            for url in self._config.webhook_urls:
                tasks.append(self._send_webhook(payload, url))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log delivery status
        statuses: list[AlertDeliveryStatus] = []
        for result in results:
            if isinstance(result, AlertDeliveryStatus):
                statuses.append(result)
                if result.success:
                    logger.info("alert_delivered", channel=result.channel)
                else:
                    logger.error(
                        "alert_delivery_failed", channel=result.channel, error=result.error
                    )
            elif isinstance(result, Exception):
                logger.error("alert_delivery_exception", error=str(result), exc_info=result)

        return statuses

    async def _send_email(self, payload: AlertPayload) -> AlertDeliveryStatus:
        """Send email alert via SMTP.

        Args:
            payload: Alert payload

        Returns:
            AlertDeliveryStatus
        """
        try:
            # Validate config
            if not self._config.smtp_host or not self._config.smtp_to:
                raise ValueError("SMTP configuration incomplete")

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"[RustyBT Alert] {payload.circuit_breaker_type.upper()} Circuit Breaker Tripped"
            )
            msg["From"] = self._config.smtp_from or self._config.smtp_username
            msg["To"] = ", ".join(self._config.smtp_to)

            # Plain text body
            text_body = f"""
RustyBT Alert: Circuit Breaker Tripped

Strategy: {payload.strategy_name}
Circuit Breaker: {payload.circuit_breaker_type}
Event Type: {payload.event_type}
Reason: {payload.reason}
Timestamp: {payload.timestamp}

Details:
{json.dumps(payload.details, indent=2)}

---
This is an automated alert from RustyBT Live Trading Engine.
"""

            # HTML body
            html_body = f"""
<html>
<head></head>
<body>
<h2 style="color: red;">⚠️ RustyBT Alert: Circuit Breaker Tripped</h2>
<table>
<tr><td><strong>Strategy:</strong></td><td>{payload.strategy_name}</td></tr>
<tr><td><strong>Circuit Breaker:</strong></td><td>{payload.circuit_breaker_type}</td></tr>
<tr><td><strong>Event Type:</strong></td><td>{payload.event_type}</td></tr>
<tr><td><strong>Reason:</strong></td><td>{payload.reason}</td></tr>
<tr><td><strong>Timestamp:</strong></td><td>{payload.timestamp}</td></tr>
</table>
<h3>Details:</h3>
<pre>{json.dumps(payload.details, indent=2)}</pre>
<hr>
<p><em>This is an automated alert from RustyBT Live Trading Engine.</em></p>
</body>
</html>
"""

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send via SMTP (run in executor since smtplib is blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_smtp_sync,
                msg,
            )

            return AlertDeliveryStatus(channel="email", success=True)

        except Exception as e:
            logger.error("email_alert_failed", error=str(e), exc_info=True)
            return AlertDeliveryStatus(channel="email", success=False, error=str(e))

    def _send_smtp_sync(self, msg: MIMEMultipart) -> None:
        """Synchronous SMTP send (runs in executor).

        Args:
            msg: Email message to send
        """
        with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
            server.starttls()
            if self._config.smtp_username and self._config.smtp_password:
                server.login(self._config.smtp_username, self._config.smtp_password)
            server.send_message(msg)

    async def _send_sms(self, payload: AlertPayload) -> AlertDeliveryStatus:
        """Send SMS alert via Twilio.

        Args:
            payload: Alert payload

        Returns:
            AlertDeliveryStatus
        """
        try:
            # Validate config
            if not self._config.twilio_account_sid or not self._config.twilio_to_numbers:
                raise ValueError("Twilio configuration incomplete")

            # Format SMS message (limited to 160 chars for standard SMS)
            message = (
                f"RustyBT Alert: {payload.circuit_breaker_type.upper()} breaker tripped "
                f"for {payload.strategy_name}. Reason: {payload.reason}"
            )[:160]

            # Twilio API endpoint
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self._config.twilio_account_sid}/Messages.json"

            # Send to all recipients
            async with aiohttp.ClientSession() as session:
                for to_number in self._config.twilio_to_numbers:
                    data = {
                        "From": self._config.twilio_from_number,
                        "To": to_number,
                        "Body": message,
                    }
                    auth = aiohttp.BasicAuth(
                        self._config.twilio_account_sid,
                        self._config.twilio_auth_token or "",
                    )
                    async with session.post(url, data=data, auth=auth) as response:
                        if response.status != 201:
                            error_text = await response.text()
                            raise Exception(f"Twilio API error: {error_text}")

            return AlertDeliveryStatus(channel="sms", success=True)

        except Exception as e:
            logger.error("sms_alert_failed", error=str(e), exc_info=True)
            return AlertDeliveryStatus(channel="sms", success=False, error=str(e))

    async def _send_webhook(self, payload: AlertPayload, url: str) -> AlertDeliveryStatus:
        """Send webhook alert to custom endpoint.

        Args:
            payload: Alert payload
            url: Webhook URL

        Returns:
            AlertDeliveryStatus
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid webhook URL: {url}")

            # Create payload JSON
            payload_json = payload.model_dump()
            payload_str = json.dumps(payload_json)

            # Create headers
            headers = {"Content-Type": "application/json"}

            # Add authentication
            if url in self._config.webhook_auth_tokens:
                headers["Authorization"] = f"Bearer {self._config.webhook_auth_tokens[url]}"

            # Add HMAC signature if configured
            if self._config.webhook_hmac_secret:
                signature = hmac.new(
                    self._config.webhook_hmac_secret.encode(),
                    payload_str.encode(),
                    hashlib.sha256,
                ).hexdigest()
                headers["X-RustyBT-Signature"] = signature

            # Send POST request
            async with (
                aiohttp.ClientSession() as session,
                session.post(url, data=payload_str, headers=headers, timeout=10) as response,
            ):
                if response.status not in (200, 201, 202, 204):
                    error_text = await response.text()
                    raise Exception(f"Webhook returned {response.status}: {error_text}")

            return AlertDeliveryStatus(channel=f"webhook:{url}", success=True)

        except Exception as e:
            logger.error("webhook_alert_failed", url=url, error=str(e), exc_info=True)
            return AlertDeliveryStatus(channel=f"webhook:{url}", success=False, error=str(e))
