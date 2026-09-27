"""Tests for heartbeats on long jobs + the refresh helper (ADR 0006, decision 2).

Long jobs (batch_weather 120s, backup 60s, retroactive_match 120s, imports 120s)
set heartbeat so SAQ's sweeper detects a crashed worker in ~2 min instead of
waiting out the full timeout. The refresh helper touches the heartbeat between
steps.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trainingdash.jobs import (
    enqueue_backup_job,
    enqueue_batch_weather_job,
    enqueue_import_garmin_job,
    enqueue_import_xert_job,
    enqueue_retroactive_match_job,
    touch_heartbeat,
)


@pytest.fixture
def mock_queue():
    with (
        patch("trainingdash.jobs.queue_available", return_value=True),
        patch("trainingdash.jobs.get_queue", new_callable=AsyncMock) as get_queue,
    ):
        queue = get_queue.return_value
        queue.enqueue = AsyncMock(return_value=type("J", (), {"key": "k"})())
        yield queue


async def test_batch_weather_heartbeat_120s(mock_queue):
    await enqueue_batch_weather_job(user_id=1)
    assert mock_queue.enqueue.call_args.kwargs["heartbeat"] == 120


async def test_backup_heartbeat_60s(mock_queue):
    await enqueue_backup_job()
    assert mock_queue.enqueue.call_args.kwargs["heartbeat"] == 60


async def test_retroactive_match_heartbeat_120s(mock_queue):
    await enqueue_retroactive_match_job(segment_id="s1")
    assert mock_queue.enqueue.call_args.kwargs["heartbeat"] == 120


async def test_import_heartbeats_120s(mock_queue):
    await enqueue_import_xert_job(user_id=1)
    await enqueue_import_garmin_job(user_id=1)
    assert mock_queue.enqueue.call_args.kwargs["heartbeat"] == 120


async def test_touch_heartbeat_calls_job_update():
    job = MagicMock()
    job.update = AsyncMock()
    await touch_heartbeat({"job": job})
    job.update.assert_awaited_once()


async def test_touch_heartbeat_tolerates_missing_job():
    """Defensive: cron/legacy ctx without a job object must not raise."""
    await touch_heartbeat({})


async def test_touch_heartbeat_tolerates_update_failure():
    """A heartbeat refresh failure must never kill a running job."""
    job = MagicMock()
    job.update = AsyncMock(side_effect=RuntimeError("db busy"))
    await touch_heartbeat({"job": job})  # must not raise
