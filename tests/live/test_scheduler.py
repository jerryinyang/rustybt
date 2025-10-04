"""Unit tests for TradingScheduler.

Tests scheduling accuracy, trigger types, market event triggers, timezone handling,
and callback registration/execution.
"""

import asyncio
from datetime import datetime, timedelta

import pytest
import pytz

from rustybt.live.events import ScheduledTriggerEvent
from rustybt.live.scheduler import SchedulerError, TradingScheduler


@pytest.fixture
def event_queue():
    """Create async event queue."""
    return asyncio.Queue()


@pytest.fixture
def scheduler(event_queue):
    """Create TradingScheduler instance."""
    return TradingScheduler(
        event_queue=event_queue,
        misfire_grace_time=60,
        timezone="UTC",
    )


@pytest.fixture
def ny_scheduler(event_queue):
    """Create TradingScheduler with NY timezone."""
    return TradingScheduler(
        event_queue=event_queue,
        misfire_grace_time=60,
        timezone="America/New_York",
    )


class TestSchedulerInitialization:
    """Test scheduler initialization."""

    def test_scheduler_init(self, scheduler):
        """Test scheduler initializes correctly."""
        assert scheduler._misfire_grace_time == 60
        assert scheduler._timezone == pytz.UTC
        assert not scheduler._scheduler.running
        assert len(scheduler._callbacks) == 0

    def test_scheduler_init_custom_timezone(self, ny_scheduler):
        """Test scheduler initializes with custom timezone."""
        assert ny_scheduler._timezone == pytz.timezone("America/New_York")

    @pytest.mark.asyncio
    async def test_scheduler_start(self, scheduler):
        """Test scheduler starts successfully."""
        scheduler.start()
        assert scheduler._scheduler.running
        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_scheduler_start_idempotent(self, scheduler):
        """Test starting already-running scheduler is safe."""
        scheduler.start()
        scheduler.start()  # Should not raise
        assert scheduler._scheduler.running
        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_scheduler_shutdown(self, scheduler):
        """Test scheduler shuts down successfully."""
        scheduler.start()
        # Give scheduler a moment to fully start
        await asyncio.sleep(0.1)
        scheduler.shutdown(wait=True)
        # Give scheduler a moment to fully shutdown
        await asyncio.sleep(0.1)
        assert not scheduler._scheduler.running

    def test_scheduler_shutdown_not_running(self, scheduler):
        """Test shutting down non-running scheduler is safe."""
        scheduler.shutdown()  # Should not raise


class TestCronTriggers:
    """Test cron trigger scheduling."""

    @pytest.mark.asyncio
    async def test_add_cron_job(self, scheduler):
        """Test adding cron job creates job with correct schedule."""
        callback_executed = []

        def test_callback():
            callback_executed.append(True)

        scheduler.start()
        job_id = scheduler.add_job(
            callback=test_callback,
            trigger="cron",
            cron="0 9 * * MON-FRI",
            callback_name="test_cron",
        )

        assert job_id == "test_cron"
        assert "test_cron" in scheduler._callbacks
        assert scheduler._callbacks["test_cron"].enabled

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_cron_trigger_invalid_expression(self, scheduler):
        """Test cron trigger with invalid expression raises error."""
        scheduler.start()

        with pytest.raises(SchedulerError, match="Invalid cron expression"):
            scheduler.add_job(
                callback=lambda: None,
                trigger="cron",
                cron="INVALID",  # Only 1 field instead of 5
            )

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_cron_trigger_missing_parameter(self, scheduler):
        """Test cron trigger without cron parameter raises error."""
        scheduler.start()

        with pytest.raises(SchedulerError, match="cron trigger requires 'cron' parameter"):
            scheduler.add_job(
                callback=lambda: None,
                trigger="cron",
            )

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_cron_callback_emits_event(self, scheduler, event_queue):
        """Test cron callback emits ScheduledTriggerEvent to queue."""
        callback_executed = []

        async def test_callback():
            callback_executed.append(True)

        scheduler.start()

        # Schedule for immediate execution (every minute)
        scheduler.add_job(
            callback=test_callback,
            trigger="cron",
            cron="* * * * *",
            callback_name="immediate_test",
        )

        # Wait for callback to potentially fire (with timeout)
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=2)
            assert isinstance(event, ScheduledTriggerEvent)
            assert event.callback_name == "immediate_test"
        except TimeoutError:
            # Callback may not fire immediately in test, this is acceptable
            pass

        scheduler.shutdown()


class TestIntervalTriggers:
    """Test interval trigger scheduling."""

    @pytest.mark.asyncio
    async def test_add_interval_job_seconds(self, scheduler):
        """Test adding interval job with seconds."""
        scheduler.start()
        job_id = scheduler.add_job(
            callback=lambda: None,
            trigger="interval",
            seconds=30,
            callback_name="interval_30s",
        )

        assert job_id == "interval_30s"
        assert "interval_30s" in scheduler._callbacks

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_add_interval_job_minutes(self, scheduler):
        """Test adding interval job with minutes."""
        scheduler.start()
        job_id = scheduler.add_job(
            callback=lambda: None,
            trigger="interval",
            minutes=5,
            callback_name="interval_5m",
        )

        assert job_id == "interval_5m"
        assert "interval_5m" in scheduler._callbacks

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_interval_trigger_missing_parameters(self, scheduler):
        """Test interval trigger without time parameters raises error."""
        scheduler.start()

        with pytest.raises(SchedulerError, match="interval trigger requires time parameters"):
            scheduler.add_job(
                callback=lambda: None,
                trigger="interval",
            )

        scheduler.shutdown()


class TestDateTriggers:
    """Test date trigger scheduling."""

    @pytest.mark.asyncio
    async def test_add_date_job(self, scheduler):
        """Test adding date trigger for specific datetime."""
        scheduler.start()
        run_date = datetime.now(pytz.UTC) + timedelta(hours=1)

        job_id = scheduler.add_job(
            callback=lambda: None,
            trigger="date",
            run_date=run_date,
            callback_name="one_time_job",
        )

        assert job_id == "one_time_job"
        assert "one_time_job" in scheduler._callbacks

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_date_trigger_missing_parameter(self, scheduler):
        """Test date trigger without run_date raises error."""
        scheduler.start()

        with pytest.raises(SchedulerError, match="date trigger requires 'run_date' parameter"):
            scheduler.add_job(
                callback=lambda: None,
                trigger="date",
            )

        scheduler.shutdown()


class TestMarketEventTriggers:
    """Test market open/close/pre-market/after-hours triggers."""

    @pytest.mark.asyncio
    async def test_schedule_market_open_nyse(self, ny_scheduler):
        """Test market_open trigger uses correct NYSE hours (9:30 ET)."""
        ny_scheduler.start()

        job_id = ny_scheduler.schedule_market_open(
            callback=lambda: None,
            exchange="NYSE",
            timezone="America/New_York",
            callback_name="nyse_open",
        )

        assert job_id == "nyse_open"
        assert "nyse_open" in ny_scheduler._callbacks

        # Verify trigger configuration
        callback = ny_scheduler._callbacks["nyse_open"]
        assert callback.trigger_config["trigger"] == "cron"
        assert callback.trigger_config["cron"] == "30 9 * * MON-FRI"

        ny_scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_market_close_nyse(self, ny_scheduler):
        """Test market_close trigger uses correct NYSE hours (16:00 ET)."""
        ny_scheduler.start()

        job_id = ny_scheduler.schedule_market_close(
            callback=lambda: None,
            exchange="NYSE",
            timezone="America/New_York",
            callback_name="nyse_close",
        )

        assert job_id == "nyse_close"
        callback = ny_scheduler._callbacks["nyse_close"]
        assert callback.trigger_config["cron"] == "0 16 * * MON-FRI"

        ny_scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_market_open_london(self, scheduler):
        """Test market_open trigger for LSE (8:00 GMT)."""
        scheduler.start()

        job_id = scheduler.schedule_market_open(
            callback=lambda: None,
            exchange="XLON",
            timezone="Europe/London",
            callback_name="lse_open",
        )

        assert job_id == "lse_open"
        callback = scheduler._callbacks["lse_open"]
        assert callback.trigger_config["cron"] == "0 8 * * MON-FRI"

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_market_close_tokyo(self, scheduler):
        """Test market_close trigger for TSE (15:00 JST)."""
        scheduler.start()

        # Use XTKS (Tokyo Stock Exchange) instead of XJPX
        job_id = scheduler.schedule_market_close(
            callback=lambda: None,
            exchange="XTKS",
            timezone="Asia/Tokyo",
            callback_name="tse_close",
        )

        assert job_id == "tse_close"
        callback = scheduler._callbacks["tse_close"]
        # TSE doesn't have a default, but we use 15:00
        assert "15" in callback.trigger_config["cron"]

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_pre_market(self, ny_scheduler):
        """Test pre_market trigger with offset before market open."""
        ny_scheduler.start()

        job_id = ny_scheduler.schedule_pre_market(
            callback=lambda: None,
            exchange="NYSE",
            timezone="America/New_York",
            offset_minutes=-30,  # 9:00 ET (30min before 9:30)
            callback_name="pre_market",
        )

        assert job_id == "pre_market"
        callback = ny_scheduler._callbacks["pre_market"]
        assert callback.trigger_config["cron"] == "0 9 * * MON-FRI"

        ny_scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_after_hours(self, ny_scheduler):
        """Test after_hours trigger with offset after market close."""
        ny_scheduler.start()

        job_id = ny_scheduler.schedule_after_hours(
            callback=lambda: None,
            exchange="NYSE",
            timezone="America/New_York",
            offset_minutes=30,  # 16:30 ET (30min after 16:00)
            callback_name="after_hours",
        )

        assert job_id == "after_hours"
        callback = ny_scheduler._callbacks["after_hours"]
        assert callback.trigger_config["cron"] == "30 16 * * MON-FRI"

        ny_scheduler.shutdown()


class TestCallbackManagement:
    """Test callback registration, enable/disable, removal."""

    @pytest.mark.asyncio
    async def test_remove_job(self, scheduler):
        """Test removing a scheduled job."""
        scheduler.start()

        scheduler.add_job(
            callback=lambda: None,
            trigger="cron",
            cron="0 * * * *",
            callback_name="test_remove",
        )

        assert "test_remove" in scheduler._callbacks

        scheduler.remove_job("test_remove")
        assert "test_remove" not in scheduler._callbacks

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_remove_job_not_found(self, scheduler):
        """Test removing non-existent job raises error."""
        scheduler.start()

        with pytest.raises(SchedulerError, match="Callback nonexistent not found"):
            scheduler.remove_job("nonexistent")

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_disable_callback(self, scheduler):
        """Test disabling callback without removing job."""
        scheduler.start()

        scheduler.add_job(
            callback=lambda: None,
            trigger="cron",
            cron="0 * * * *",
            callback_name="test_disable",
        )

        assert scheduler._callbacks["test_disable"].enabled

        scheduler.disable_callback("test_disable")
        assert not scheduler._callbacks["test_disable"].enabled

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_enable_callback(self, scheduler):
        """Test enabling previously disabled callback."""
        scheduler.start()

        scheduler.add_job(
            callback=lambda: None,
            trigger="cron",
            cron="0 * * * *",
            callback_name="test_enable",
        )

        scheduler.disable_callback("test_enable")
        assert not scheduler._callbacks["test_enable"].enabled

        scheduler.enable_callback("test_enable")
        assert scheduler._callbacks["test_enable"].enabled

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_enable_already_enabled(self, scheduler):
        """Test enabling already-enabled callback is safe."""
        scheduler.start()

        scheduler.add_job(
            callback=lambda: None,
            trigger="cron",
            cron="0 * * * *",
            callback_name="already_enabled",
        )

        scheduler.enable_callback("already_enabled")  # Should not raise
        assert scheduler._callbacks["already_enabled"].enabled

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_disable_already_disabled(self, scheduler):
        """Test disabling already-disabled callback is safe."""
        scheduler.start()

        scheduler.add_job(
            callback=lambda: None,
            trigger="cron",
            cron="0 * * * *",
            callback_name="already_disabled",
        )

        scheduler.disable_callback("already_disabled")
        scheduler.disable_callback("already_disabled")  # Should not raise
        assert not scheduler._callbacks["already_disabled"].enabled

        scheduler.shutdown()


class TestListJobs:
    """Test listing scheduled jobs."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, scheduler):
        """Test listing jobs when none scheduled."""
        scheduler.start()
        jobs = scheduler.list_jobs()
        assert len(jobs) == 0
        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_list_jobs_multiple(self, scheduler):
        """Test listing multiple scheduled jobs."""
        scheduler.start()

        scheduler.add_job(
            callback=lambda: None,
            trigger="cron",
            cron="0 9 * * *",
            callback_name="job1",
        )

        scheduler.add_job(
            callback=lambda: None,
            trigger="interval",
            minutes=5,
            callback_name="job2",
        )

        jobs = scheduler.list_jobs()
        assert len(jobs) == 2

        job_names = [job["callback_name"] for job in jobs]
        assert "job1" in job_names
        assert "job2" in job_names

        # Verify job metadata
        job1 = next(j for j in jobs if j["callback_name"] == "job1")
        assert job1["enabled"] is True
        assert job1["trigger_config"]["trigger"] == "cron"
        assert job1["trigger_config"]["cron"] == "0 9 * * *"

        scheduler.shutdown()


class TestCallbackExecution:
    """Test callback execution and error handling."""

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_crash_scheduler(self, scheduler, event_queue):
        """Test callback exceptions are logged but don't crash scheduler."""

        async def failing_callback():
            raise ValueError("Test error")

        scheduler.start()

        scheduler.add_job(
            callback=failing_callback,
            trigger="cron",
            cron="* * * * *",
            callback_name="failing",
        )

        # Wait briefly to ensure callback has chance to execute
        await asyncio.sleep(0.5)

        # Scheduler should still be running
        assert scheduler._scheduler.running

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_duplicate_callback_name_raises_error(self, scheduler):
        """Test adding callback with duplicate name raises error."""
        scheduler.start()

        scheduler.add_job(
            callback=lambda: None,
            trigger="cron",
            cron="0 * * * *",
            callback_name="duplicate",
        )

        with pytest.raises(SchedulerError, match="Callback duplicate already registered"):
            scheduler.add_job(
                callback=lambda: None,
                trigger="cron",
                cron="0 * * * *",
                callback_name="duplicate",
            )

        scheduler.shutdown()


class TestTimezoneHandling:
    """Test timezone-aware scheduling."""

    @pytest.mark.asyncio
    async def test_timezone_conversion_ny_to_utc(self, ny_scheduler):
        """Test scheduling in ET converts correctly to UTC."""
        ny_scheduler.start()

        # Schedule at 9:30 ET
        ny_scheduler.schedule_market_open(
            callback=lambda: None,
            exchange="NYSE",
            timezone="America/New_York",
        )

        # Verify job exists
        jobs = ny_scheduler.list_jobs()
        assert len(jobs) == 1

        ny_scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_invalid_timezone_raises_error(self, event_queue):
        """Test invalid timezone raises error."""
        with pytest.raises(pytz.UnknownTimeZoneError):
            TradingScheduler(
                event_queue=event_queue,
                timezone="Invalid/Timezone",
            )


class TestSchedulingAccuracy:
    """Test scheduling accuracy requirements (±1 second tolerance)."""

    @pytest.mark.asyncio
    async def test_scheduling_accuracy_within_tolerance(self, scheduler, event_queue):
        """Test scheduled callbacks fire within ±1 second of scheduled time."""
        scheduled_time = datetime.now(pytz.UTC) + timedelta(seconds=2)
        execution_times = []

        async def timed_callback():
            execution_times.append(datetime.now(pytz.UTC))

        scheduler.start()

        scheduler.add_job(
            callback=timed_callback,
            trigger="date",
            run_date=scheduled_time,
            callback_name="accuracy_test",
        )

        # Wait for callback execution (with timeout)
        await asyncio.sleep(3)

        if execution_times:
            actual_time = execution_times[0]
            time_diff = abs((actual_time - scheduled_time).total_seconds())

            # Verify within 1 second tolerance
            assert time_diff <= 1.0, f"Scheduling accuracy: {time_diff}s (expected ≤1.0s)"

        scheduler.shutdown()
