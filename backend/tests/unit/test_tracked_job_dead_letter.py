"""Tests for tracked_job dead-letter recording (ADR 0006, decision 1).

When a job's final attempt fails (attempts exhausted), the wrapper records a
durable dead-letter job.failed event carrying the job name, key, args, attempts,
and truncated error — SAQ TTL-deletes terminal rows after 600s, so this is the
permanent failure record.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trainingdash.worker import tracked_job


def _ctx(attempts: int, retries: int = 3, job_key: str = "job-key-1"):
    """SAQ worker context carrying a job object mid-flight."""
    job = MagicMock()
    job.attempts = attempts
    job.retries = retries
    job.key = job_key
    return {"job": job}


@pytest.fixture
def capture_events(monkeypatch):
    """Capture events written through the event repo; returns (repo, events)."""
    events: list[dict] = []

    repo = MagicMock()
    repo.log = AsyncMock()

    class FakeSession:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("trainingdash.worker.worker_db_session", lambda ctx: FakeSession())
    monkeypatch.setattr(
        "trainingdash.repositories.postgres.event_repo.PostgresEventRepo", lambda db: repo
    )
    return repo


async def test_dead_letter_event_on_final_attempt(capture_events):
    """attempts (4) >= retries (3) → terminal failure → dead_letter marker in payload."""

    @tracked_job("ingest")
    async def failing(ctx, **kwargs):
        raise ValueError("parse blew up")

    with pytest.raises(ValueError):
        await failing(_ctx(attempts=4, retries=3))

    calls = [c for c in capture_events.log.call_args_list if c.kwargs.get("event_type") == "job.failed"]
    assert len(calls) == 1
    payload = calls[0].kwargs["payload"]
    assert payload["dead_letter"] is True
    assert payload["job_name"] == "ingest"
    assert payload["job_key"] == "job-key-1"
    assert payload["attempts"] == 4
    assert "parse blew" in payload["error"]


async def test_no_dead_letter_on_retryable_failure(capture_events):
    """attempts (2) < retries (3) → SAQ will retry; event has no dead_letter marker."""
    from trainingdash.worker import tracked_job

    @tracked_job("import_xert")
    async def failing(ctx, **kwargs):
        raise RuntimeError("provider 5xx")

    with pytest.raises(RuntimeError):
        await failing(_ctx(attempts=2, retries=3))

    calls = [c for c in capture_events.log.call_args_list if c.kwargs.get("event_type") == "job.failed"]
    assert len(calls) == 1
    payload = calls[0].kwargs["payload"]
    assert payload.get("dead_letter") is not True
    assert payload["attempts"] == 2


async def test_dead_letter_payload_carries_kwargs(capture_events):
    """Retry (ADR 0007) re-enqueues from the event payload — args must be present."""

    @tracked_job("match_route")
    async def failing(ctx, **kwargs):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await failing(_ctx(attempts=4), activity_id="a1", user_id=7)

    payload = [
        c.kwargs["payload"]
        for c in capture_events.log.call_args_list
        if c.kwargs.get("event_type") == "job.failed"
    ][0]
    assert payload["kwargs"] == {"activity_id": "a1", "user_id": 7}


async def test_completed_job_has_no_dead_letter(capture_events):
    @tracked_job("ingest")
    async def ok(ctx, **kwargs):
        return {"success": True}

    await ok(_ctx(attempts=1))

    calls = [c for c in capture_events.log.call_args_list if c.kwargs.get("event_type") == "job.failed"]
    assert calls == []


async def test_no_job_in_ctx_still_logs_failure_without_dead_letter_fields(capture_events):
    """Defensive: cron/legacy ctx without a job object must still log, without dead-letter."""

    @tracked_job("weird")
    async def failing(ctx, **kwargs):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await failing({})

    calls = [c for c in capture_events.log.call_args_list if c.kwargs.get("event_type") == "job.failed"]
    assert len(calls) == 1
    payload = calls[0].kwargs["payload"]
    assert payload.get("dead_letter") is not True
    assert payload["error"] == "boom"