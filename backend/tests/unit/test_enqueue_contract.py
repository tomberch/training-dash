"""Tests for the enqueue helper contract (ADR 0006, decision 3).

- None on no-queue mode (dev convenience, never fires in production)
- EnqueueError on real enqueue failures (never swallowed)
- key parameter passthrough for hour-bucketed scheduler dedup
"""

from unittest.mock import AsyncMock, patch

import pytest

from trainingdash.jobs import (
    EnqueueError,
    enqueue_backup_job,
    enqueue_batch_weather_job,
    enqueue_import_xert_job,
    enqueue_match_route_job,
    enqueue_recalculate_metrics_job,
)


@pytest.fixture
def mock_queue():
    """A connected SAQ queue mock for real (non-fallback) enqueue calls."""
    with patch("trainingdash.jobs.queue_available", return_value=True), patch(
        "trainingdash.jobs.get_queue", new_callable=AsyncMock
    ) as get_queue:
        queue = get_queue.return_value
        queue.enqueue = AsyncMock(return_value=type("J", (), {"key": "job-key"})())
        yield queue


async def test_none_when_queue_unavailable_is_dev_signal():
    """queue_available()=False → None (dev/no-queue mode), no exception."""
    with patch("trainingdash.jobs.queue_available", return_value=False):
        assert await enqueue_import_xert_job(user_id=1) is None


async def test_enqueue_error_when_enqueue_raises(mock_queue):
    """A real enqueue failure raises EnqueueError — never a raw SAQ error."""
    mock_queue.enqueue.side_effect = RuntimeError("connection refused")
    with pytest.raises(EnqueueError, match="connection refused"):
        await enqueue_import_xert_job(user_id=1)


async def test_enqueue_error_wrapped_on_batch_weather(mock_queue):
    mock_queue.enqueue.side_effect = RuntimeError("db down")
    with pytest.raises(EnqueueError):
        await enqueue_batch_weather_job(user_id=1)


async def test_key_param_passed_through(mock_queue):
    """The key kwarg reaches SAQ's enqueue (hour-bucketed scheduler dedup)."""
    await enqueue_import_xert_job(user_id=7, key="import:xert:7:2026-09-27T09")
    assert mock_queue.enqueue.call_args.kwargs.get("key") == "import:xert:7:2026-09-27T09"


async def test_default_key_is_none(mock_queue):
    """No key passed → SAQ auto-generates one (manual triggers must always fire)."""
    await enqueue_import_xert_job(user_id=7)
    assert "key" not in mock_queue.enqueue.call_args.kwargs or (
        mock_queue.enqueue.call_args.kwargs.get("key") is None
    )


async def test_match_route_job_raises_enqueue_error(mock_queue):
    """Chain steps must never swallow: they need the failure to log/event."""
    mock_queue.enqueue.side_effect = RuntimeError("pool exhausted")
    with pytest.raises(EnqueueError):
        await enqueue_match_route_job(activity_id="a1", user_id=1)


async def test_recalculate_job_raises_enqueue_error(mock_queue):
    mock_queue.enqueue.side_effect = RuntimeError("pool exhausted")
    with pytest.raises(EnqueueError):
        await enqueue_recalculate_metrics_job(user_id=1)


async def test_backup_job_raises_enqueue_error(mock_queue):
    mock_queue.enqueue.side_effect = RuntimeError("pool exhausted")
    with pytest.raises(EnqueueError):
        await enqueue_backup_job()


async def test_retry_settings_on_import_job(mock_queue):
    """Imports: retries=3, retry_delay=30, retry_backoff=300 (ADR 0006 D1)."""
    await enqueue_import_xert_job(user_id=1)
    kwargs = mock_queue.enqueue.call_args.kwargs
    assert kwargs["retries"] == 3
    assert kwargs["retry_delay"] == 30
    assert kwargs["retry_backoff"] == 300


async def test_backup_job_retries_1_for_sweep_exemption(mock_queue):
    """Backup never auto-retries after a sweep (ADR 0006 D2) — retries=1."""
    await enqueue_backup_job()
    kwargs = mock_queue.enqueue.call_args.kwargs
    assert kwargs["retries"] == 1


async def test_group_keys_on_long_jobs(mock_queue):
    """Long job classes get group_key caps (ADR 0006 D4)."""
    await enqueue_batch_weather_job(user_id=1)
    assert mock_queue.enqueue.call_args.kwargs["group_key"] == "batch_weather"