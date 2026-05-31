"""Tests for scheduler_service — job scheduling and lifecycle."""
import json
from unittest.mock import MagicMock, patch

import pytest

from needradar.models.scheduled_job import JobStatus, ScheduledJob


@pytest.fixture(autouse=True)
def clean_scheduler():
    """Reset the global scheduler singleton before each test."""
    import needradar.services.scheduler_service as mod
    mod._scheduler = None
    yield
    mod._scheduler = None


# ---------------------------------------------------------------------------
# _job_id
# ---------------------------------------------------------------------------

class TestJobId:
    def test_formats_id(self):
        from needradar.services.scheduler_service import _job_id
        assert _job_id(42) == "nr_job_42"


# ---------------------------------------------------------------------------
# get_scheduler
# ---------------------------------------------------------------------------

class TestGetScheduler:
    def test_returns_singleton(self):
        from needradar.services.scheduler_service import get_scheduler
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

    def test_creates_async_io_scheduler(self):
        from needradar.services.scheduler_service import get_scheduler
        sched = get_scheduler()
        assert sched is not None


# ---------------------------------------------------------------------------
# start_scheduler / stop_scheduler
# ---------------------------------------------------------------------------

class TestSchedulerLifecycle:
    def test_start_when_not_running(self):
        from needradar.services.scheduler_service import get_scheduler, start_scheduler
        sched = get_scheduler()
        with patch.object(sched, "start") as mock_start:
            mock_start.return_value = None
            start_scheduler()
            mock_start.assert_called_once()

    def test_start_when_already_running(self):
        import needradar.services.scheduler_service as mod
        sched = MagicMock()
        sched.running = True
        mod._scheduler = sched
        mod.start_scheduler()
        sched.start.assert_not_called()

    def test_stop_when_running(self):
        import needradar.services.scheduler_service as mod
        sched = MagicMock()
        sched.running = True
        mod._scheduler = sched
        mod.stop_scheduler()
        sched.shutdown.assert_called_once_with(wait=False)

    def test_stop_when_not_running(self):
        import needradar.services.scheduler_service as mod
        sched = MagicMock()
        sched.running = False
        mod._scheduler = sched
        mod.stop_scheduler()
        sched.shutdown.assert_not_called()


# ---------------------------------------------------------------------------
# remove_job / reschedule_job
# ---------------------------------------------------------------------------

class TestRemoveJob:
    def test_removes_existing_job(self):
        import needradar.services.scheduler_service as mod
        sched = MagicMock()
        mod._scheduler = sched
        mod.remove_job(42)
        sched.remove_job.assert_called_once_with("nr_job_42")

    def test_handles_missing_job(self):
        import needradar.services.scheduler_service as mod
        sched = MagicMock()
        sched.remove_job.side_effect = ValueError("job not found")
        mod._scheduler = sched
        mod.remove_job(42)  # should not raise


class TestRescheduleJob:
    def test_reschedules_existing_job(self):
        import needradar.services.scheduler_service as mod
        sched = MagicMock()
        mod._scheduler = sched
        mod.reschedule_job(42, interval_minutes=30)
        sched.reschedule_job.assert_called_once()
        call_args = sched.reschedule_job.call_args
        assert call_args[0][0] == "nr_job_42"

    def test_handles_missing_job(self):
        import needradar.services.scheduler_service as mod
        sched = MagicMock()
        sched.reschedule_job.side_effect = ValueError("job not found")
        mod._scheduler = sched
        mod.reschedule_job(42, interval_minutes=60)  # should not raise


# ---------------------------------------------------------------------------
# _add_job_to_scheduler
# ---------------------------------------------------------------------------

class TestAddJobToScheduler:
    @pytest.mark.asyncio
    async def test_adds_job_with_interval(self, db_session):
        from needradar.services.scheduler_service import _add_job_to_scheduler
        job = ScheduledJob(
            name="Test Job",
            keyword="python",
            platforms=json.dumps(["github"]),
            interval_minutes=60,
            status=JobStatus.ACTIVE,
        )
        db_session.add(job)
        await db_session.flush()

        sched = MagicMock()
        _add_job_to_scheduler(sched, job)
        sched.add_job.assert_called_once()
        call_kwargs = sched.add_job.call_args[1]
        assert call_kwargs["id"] == f"nr_job_{job.id}"
        assert call_kwargs["args"] == [job.id]

    def test_removes_existing_before_adding(self):
        from needradar.services.scheduler_service import _add_job_to_scheduler
        job = MagicMock()
        job.id = 7
        job.interval_minutes = 30
        sched = MagicMock()
        _add_job_to_scheduler(sched, job)
        sched.remove_job.assert_called_once_with("nr_job_7")
        sched.add_job.assert_called_once()

    def test_handles_remove_failure(self):
        from needradar.services.scheduler_service import _add_job_to_scheduler
        job = MagicMock()
        job.id = 7
        job.interval_minutes = 30
        sched = MagicMock()
        sched.remove_job.side_effect = RuntimeError("no such job")
        _add_job_to_scheduler(sched, job)
        sched.add_job.assert_called_once()
