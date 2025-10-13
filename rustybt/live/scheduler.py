"""Trading scheduler for periodic tasks and market event triggers.

This module provides scheduling capabilities for live trading strategies using APScheduler.
Supports cron-like expressions, market event triggers (market_open, market_close), and
timezone-aware scheduling with trading calendar integration.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Any

import pandas as pd
import pytz
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from exchange_calendars import ExchangeCalendar, get_calendar
from pydantic import BaseModel, Field

from rustybt.live.events import ScheduledTriggerEvent

logger = structlog.get_logger(__name__)


class SchedulerError(Exception):
    """Raised when scheduler operations fail."""

    pass


class ScheduledCallback(BaseModel):
    """Configuration for a scheduled callback.

    Attributes:
        callback_name: Unique name for the callback
        callback_func: Callable to execute on trigger
        trigger_config: Trigger configuration (cron, interval, etc.)
        enabled: Whether callback is active
        job_id: APScheduler job ID (set after registration)
    """

    callback_name: str = Field(..., description="Unique callback identifier")
    callback_func: Callable = Field(..., description="Function to execute")
    trigger_config: dict[str, Any] = Field(
        default_factory=dict, description="Trigger configuration"
    )
    enabled: bool = Field(True, description="Whether callback is enabled")
    job_id: str | None = Field(None, description="APScheduler job ID")

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        frozen = False


class TradingScheduler:
    """Scheduler for trading strategy callbacks and market event triggers.

    Integrates APScheduler for cron-like scheduling with trading calendar support
    for market hours, holidays, and exchange-specific timezones.

    Example:
        >>> scheduler = TradingScheduler(event_queue=queue)
        >>> scheduler.start()
        >>> # Schedule daily rebalancing at market close
        >>> scheduler.schedule_market_close(
        ...     callback=rebalance_portfolio,
        ...     exchange='NYSE',
        ...     timezone='America/New_York'
        ... )
        >>> # Schedule hourly risk check
        >>> scheduler.add_job(
        ...     trigger='cron',
        ...     callback=check_risk,
        ...     cron='0 * * * *'
        ... )
    """

    def __init__(
        self,
        event_queue: asyncio.Queue,
        misfire_grace_time: int = 60,
        timezone: str = "UTC",
    ) -> None:
        """Initialize trading scheduler.

        Args:
            event_queue: Async queue for emitting ScheduledTriggerEvents
            misfire_grace_time: Seconds to allow late trigger execution (default: 60)
            timezone: Default timezone for scheduling (default: UTC)
        """
        self._event_queue = event_queue
        self._misfire_grace_time = misfire_grace_time
        self._timezone = pytz.timezone(timezone)
        self._scheduler = AsyncIOScheduler(timezone=timezone)
        self._callbacks: dict[str, ScheduledCallback] = {}
        self._trading_calendars: dict[str, ExchangeCalendar] = {}

        logger.info(
            "scheduler_initialized",
            misfire_grace_time=misfire_grace_time,
            timezone=timezone,
        )

    def start(self) -> None:
        """Start the scheduler."""
        if self._scheduler.running:
            logger.warning("scheduler_already_running")
            return

        self._scheduler.start()
        logger.info("scheduler_started", job_count=len(self._callbacks))

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete
        """
        if not self._scheduler.running:
            logger.warning("scheduler_not_running")
            return

        self._scheduler.shutdown(wait=wait)
        logger.info("scheduler_shutdown", wait=wait)

    def add_job(
        self,
        callback: Callable,
        trigger: str,
        callback_name: str | None = None,
        **trigger_kwargs: Any,  # noqa: ANN401
    ) -> str:
        """Add a scheduled job with flexible trigger configuration.

        Args:
            callback: Function to execute on trigger
            trigger: Trigger type ('cron', 'interval', 'date')
            callback_name: Unique name for callback (auto-generated if None)
            **trigger_kwargs: Trigger-specific configuration:
                - cron: cron expression string (e.g., '0 9 * * MON-FRI')
                - interval: timedelta or seconds/minutes/hours/days/weeks
                - date: specific datetime to run once

        Returns:
            Job ID for the scheduled job

        Raises:
            SchedulerError: If trigger configuration is invalid

        Example:
            >>> # Cron: every 15 minutes during market hours
            >>> scheduler.add_job(
            ...     callback=signal_check,
            ...     trigger='cron',
            ...     cron='*/15 9-16 * * MON-FRI'
            ... )
            >>> # Interval: every 5 minutes
            >>> scheduler.add_job(
            ...     callback=data_refresh,
            ...     trigger='interval',
            ...     minutes=5
            ... )
            >>> # Date: run once at specific time
            >>> scheduler.add_job(
            ...     callback=end_of_day_report,
            ...     trigger='date',
            ...     run_date=datetime(2025, 10, 3, 16, 0)
            ... )
        """
        if callback_name is None:
            callback_name = f"{callback.__name__}_{id(callback)}"

        if callback_name in self._callbacks:
            raise SchedulerError(f"Callback {callback_name} already registered")

        # Create trigger based on type
        if trigger == "cron":
            if "cron" not in trigger_kwargs:
                raise SchedulerError("cron trigger requires 'cron' parameter")
            cron_expr = trigger_kwargs["cron"]
            # Parse cron expression: minute hour day month day_of_week
            parts = cron_expr.split()
            if len(parts) != 5:
                raise SchedulerError(f"Invalid cron expression: {cron_expr} (expected 5 fields)")
            minute, hour, day, month, day_of_week = parts
            apscheduler_trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=self._timezone,
            )
        elif trigger == "interval":
            # Extract interval parameters
            interval_params = {
                k: v
                for k, v in trigger_kwargs.items()
                if k in ["weeks", "days", "hours", "minutes", "seconds"]
            }
            if not interval_params:
                raise SchedulerError("interval trigger requires time parameters")
            apscheduler_trigger = IntervalTrigger(**interval_params, timezone=self._timezone)
        elif trigger == "date":
            if "run_date" not in trigger_kwargs:
                raise SchedulerError("date trigger requires 'run_date' parameter")
            apscheduler_trigger = DateTrigger(
                run_date=trigger_kwargs["run_date"], timezone=self._timezone
            )
        else:
            raise SchedulerError(f"Unsupported trigger type: {trigger}")

        # Wrap callback to emit event to queue
        async def wrapped_callback() -> None:
            """Execute callback and emit event to event queue."""
            try:
                logger.debug(
                    "scheduled_callback_firing",
                    callback_name=callback_name,
                    scheduled_time=datetime.now(self._timezone).isoformat(),
                )

                # Emit event to engine event queue
                event = ScheduledTriggerEvent(
                    callback_name=callback_name,
                    callback_args={},
                    trigger_timestamp=pd.Timestamp.now(tz=self._timezone),
                )
                await self._event_queue.put(event)

                # Execute callback
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()

                logger.info("scheduled_callback_executed", callback_name=callback_name)
            except Exception as e:
                logger.error(
                    "scheduled_callback_error",
                    callback_name=callback_name,
                    error=str(e),
                    exc_info=True,
                )

        # Add job to APScheduler
        job = self._scheduler.add_job(
            wrapped_callback,
            trigger=apscheduler_trigger,
            id=callback_name,
            misfire_grace_time=self._misfire_grace_time,
            coalesce=True,  # Combine multiple missed runs into one
            max_instances=1,  # Prevent concurrent execution
        )

        # Store callback metadata
        scheduled_callback = ScheduledCallback(
            callback_name=callback_name,
            callback_func=callback,
            trigger_config={"trigger": trigger, **trigger_kwargs},
            enabled=True,
            job_id=job.id,
        )
        self._callbacks[callback_name] = scheduled_callback

        logger.info(
            "job_added",
            callback_name=callback_name,
            trigger=trigger,
            trigger_config=trigger_kwargs,
            job_id=job.id,
        )

        return job.id

    def remove_job(self, callback_name: str) -> None:
        """Remove a scheduled job.

        Args:
            callback_name: Name of callback to remove

        Raises:
            SchedulerError: If callback not found
        """
        if callback_name not in self._callbacks:
            raise SchedulerError(f"Callback {callback_name} not found")

        job_id = self._callbacks[callback_name].job_id
        if job_id:
            self._scheduler.remove_job(job_id)

        del self._callbacks[callback_name]

        logger.info("job_removed", callback_name=callback_name, job_id=job_id)

    def enable_callback(self, callback_name: str) -> None:
        """Enable a previously disabled callback.

        Args:
            callback_name: Name of callback to enable

        Raises:
            SchedulerError: If callback not found
        """
        if callback_name not in self._callbacks:
            raise SchedulerError(f"Callback {callback_name} not found")

        callback = self._callbacks[callback_name]
        if callback.enabled:
            logger.warning("callback_already_enabled", callback_name=callback_name)
            return

        if callback.job_id:
            self._scheduler.resume_job(callback.job_id)

        callback.enabled = True
        logger.info("callback_enabled", callback_name=callback_name)

    def disable_callback(self, callback_name: str) -> None:
        """Disable a callback without removing it.

        Args:
            callback_name: Name of callback to disable

        Raises:
            SchedulerError: If callback not found
        """
        if callback_name not in self._callbacks:
            raise SchedulerError(f"Callback {callback_name} not found")

        callback = self._callbacks[callback_name]
        if not callback.enabled:
            logger.warning("callback_already_disabled", callback_name=callback_name)
            return

        if callback.job_id:
            self._scheduler.pause_job(callback.job_id)

        callback.enabled = False
        logger.info("callback_disabled", callback_name=callback_name)

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all active scheduled jobs.

        Returns:
            List of job metadata dictionaries
        """
        jobs = []
        for callback in self._callbacks.values():
            job_info = {
                "callback_name": callback.callback_name,
                "trigger_config": callback.trigger_config,
                "enabled": callback.enabled,
                "job_id": callback.job_id,
            }
            # Get next run time from APScheduler
            if callback.job_id:
                apscheduler_job = self._scheduler.get_job(callback.job_id)
                if apscheduler_job:
                    job_info["next_run_time"] = (
                        apscheduler_job.next_run_time.isoformat()
                        if apscheduler_job.next_run_time
                        else None
                    )
            jobs.append(job_info)

        return jobs

    def _get_trading_calendar(self, exchange: str) -> ExchangeCalendar:
        """Get or create trading calendar for exchange.

        Args:
            exchange: Exchange name (e.g., 'NYSE', 'XLON', 'XJPX')

        Returns:
            ExchangeCalendar instance

        Raises:
            SchedulerError: If calendar not found
        """
        if exchange not in self._trading_calendars:
            try:
                calendar = get_calendar(exchange)
                self._trading_calendars[exchange] = calendar
                logger.info("trading_calendar_loaded", exchange=exchange)
            except Exception as e:
                raise SchedulerError(f"Failed to load calendar for {exchange}: {e}") from e

        return self._trading_calendars[exchange]

    def schedule_market_open(
        self,
        callback: Callable,
        exchange: str = "NYSE",
        timezone: str = "America/New_York",
        callback_name: str | None = None,
    ) -> str:
        """Schedule callback at market open.

        Args:
            callback: Function to execute at market open
            exchange: Exchange name for calendar lookup (default: NYSE)
            timezone: Exchange timezone (default: America/New_York)
            callback_name: Unique callback name (auto-generated if None)

        Returns:
            Job ID

        Raises:
            SchedulerError: If calendar or timezone invalid

        Example:
            >>> scheduler.schedule_market_open(
            ...     callback=pre_market_analysis,
            ...     exchange='NYSE',
            ...     timezone='America/New_York'
            ... )
        """
        self._get_trading_calendar(exchange)

        # Get market open time (typically 9:30 for NYSE)
        # Note: exchange-calendars doesn't expose open_time directly, we'll use cron
        # For NYSE: 9:30 ET Monday-Friday
        if exchange == "NYSE":
            market_open_time = time(9, 30)
        elif exchange == "XLON":  # London Stock Exchange
            market_open_time = time(8, 0)
        elif exchange == "XJPX":  # Tokyo Stock Exchange
            market_open_time = time(9, 0)
        else:
            # Default to 9:30
            market_open_time = time(9, 30)
            logger.warning(
                "unknown_exchange_using_default_open_time",
                exchange=exchange,
                default_open=market_open_time.isoformat(),
            )

        # Convert to timezone-aware cron
        pytz.timezone(timezone)
        cron_expr = f"{market_open_time.minute} {market_open_time.hour} * * MON-FRI"

        if callback_name is None:
            callback_name = f"market_open_{exchange}_{id(callback)}"

        return self.add_job(
            callback=callback,
            trigger="cron",
            callback_name=callback_name,
            cron=cron_expr,
        )

    def schedule_market_close(
        self,
        callback: Callable,
        exchange: str = "NYSE",
        timezone: str = "America/New_York",
        callback_name: str | None = None,
    ) -> str:
        """Schedule callback at market close.

        Args:
            callback: Function to execute at market close
            exchange: Exchange name for calendar lookup (default: NYSE)
            timezone: Exchange timezone (default: America/New_York)
            callback_name: Unique callback name (auto-generated if None)

        Returns:
            Job ID

        Raises:
            SchedulerError: If calendar or timezone invalid

        Example:
            >>> scheduler.schedule_market_close(
            ...     callback=daily_rebalance,
            ...     exchange='NYSE',
            ...     timezone='America/New_York'
            ... )
        """
        self._get_trading_calendar(exchange)

        # Get market close time (typically 16:00 for NYSE)
        if exchange == "NYSE":
            market_close_time = time(16, 0)
        elif exchange == "XLON":  # London Stock Exchange
            market_close_time = time(16, 30)
        elif exchange in ("XTKS", "XJPX"):  # Tokyo Stock Exchange
            market_close_time = time(15, 0)
        else:
            # Default to 16:00
            market_close_time = time(16, 0)
            logger.warning(
                "unknown_exchange_using_default_close_time",
                exchange=exchange,
                default_close=market_close_time.isoformat(),
            )

        # Convert to timezone-aware cron
        pytz.timezone(timezone)
        cron_expr = f"{market_close_time.minute} {market_close_time.hour} * * MON-FRI"

        if callback_name is None:
            callback_name = f"market_close_{exchange}_{id(callback)}"

        return self.add_job(
            callback=callback,
            trigger="cron",
            callback_name=callback_name,
            cron=cron_expr,
        )

    def schedule_pre_market(
        self,
        callback: Callable,
        exchange: str = "NYSE",
        timezone: str = "America/New_York",  # noqa: ARG002
        offset_minutes: int = -30,
        callback_name: str | None = None,
    ) -> str:
        """Schedule callback before market open.

        Args:
            callback: Function to execute before market open
            exchange: Exchange name for calendar lookup (default: NYSE)
            timezone: Exchange timezone (default: America/New_York)
            offset_minutes: Minutes before market open (negative value, default: -30)
            callback_name: Unique callback name (auto-generated if None)

        Returns:
            Job ID

        Example:
            >>> scheduler.schedule_pre_market(
            ...     callback=pre_market_scan,
            ...     exchange='NYSE',
            ...     offset_minutes=-30  # 9:00 ET (30min before 9:30 open)
            ... )
        """
        self._get_trading_calendar(exchange)

        # Get market open time and apply offset
        if exchange == "NYSE":
            market_open_time = time(9, 30)
        elif exchange == "XLON":
            market_open_time = time(8, 0)
        elif exchange == "XJPX":
            market_open_time = time(9, 0)
        else:
            market_open_time = time(9, 30)

        # Calculate pre-market time
        pre_market_dt = datetime.combine(datetime.today(), market_open_time) + timedelta(
            minutes=offset_minutes
        )
        pre_market_time = pre_market_dt.time()

        cron_expr = f"{pre_market_time.minute} {pre_market_time.hour} * * MON-FRI"

        if callback_name is None:
            callback_name = f"pre_market_{exchange}_{id(callback)}"

        return self.add_job(
            callback=callback,
            trigger="cron",
            callback_name=callback_name,
            cron=cron_expr,
        )

    def schedule_after_hours(
        self,
        callback: Callable,
        exchange: str = "NYSE",
        timezone: str = "America/New_York",  # noqa: ARG002
        offset_minutes: int = 30,
        callback_name: str | None = None,
    ) -> str:
        """Schedule callback after market close.

        Args:
            callback: Function to execute after market close
            exchange: Exchange name for calendar lookup (default: NYSE)
            timezone: Exchange timezone (default: America/New_York)
            offset_minutes: Minutes after market close (positive value, default: 30)
            callback_name: Unique callback name (auto-generated if None)

        Returns:
            Job ID

        Example:
            >>> scheduler.schedule_after_hours(
            ...     callback=post_market_analysis,
            ...     exchange='NYSE',
            ...     offset_minutes=30  # 16:30 ET (30min after 16:00 close)
            ... )
        """
        self._get_trading_calendar(exchange)

        # Get market close time and apply offset
        if exchange == "NYSE":
            market_close_time = time(16, 0)
        elif exchange == "XLON":
            market_close_time = time(16, 30)
        elif exchange == "XJPX":
            market_close_time = time(15, 0)
        else:
            market_close_time = time(16, 0)

        # Calculate after-hours time
        after_hours_dt = datetime.combine(datetime.today(), market_close_time) + timedelta(
            minutes=offset_minutes
        )
        after_hours_time = after_hours_dt.time()

        cron_expr = f"{after_hours_time.minute} {after_hours_time.hour} * * MON-FRI"

        if callback_name is None:
            callback_name = f"after_hours_{exchange}_{id(callback)}"

        return self.add_job(
            callback=callback,
            trigger="cron",
            callback_name=callback_name,
            cron=cron_expr,
        )
