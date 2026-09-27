"""Integration tests for the admin job-operations API (ADR 0007 / ticket #691).

- GET /api/admin/system/jobs grows failed/aborted statuses + attempts + worker liveness
- POST /api/admin/system/jobs/{key}/abort
- POST /api/admin/system/jobs/{key}/retry (re-enqueue from dead-letter args)
"""

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _database_url_env(monkeypatch, db_session):
    """Point trainingdash.queue at the test DB (the app's DATABASE_URL is unset in tests)."""
    import os

    monkeypatch.setenv(
        "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/test")
    )
    yield


@pytest.fixture(autouse=True)
def _reset_queue_singleton():
    """Reset the queue singleton between tests so each test gets the patched URL."""
    from trainingdash import queue as queue_mod

    queue_mod._get_queue_instance.cache_clear()
    yield
    queue_mod._get_queue_instance.cache_clear()


_SAQ_TABLE = """
CREATE TABLE IF NOT EXISTS saq_jobs (
    key TEXT PRIMARY KEY,
    lock_key BIGSERIAL NOT NULL,
    job BYTEA NOT NULL,
    queue TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL,
    priority SMALLINT NOT NULL DEFAULT 0,
    group_key TEXT,
    scheduled BIGINT NOT NULL DEFAULT (EXTRACT(epoch FROM now())::bigint),
    expire_at BIGINT
)
"""


async def _ensure_saq_table(db_session):
    await db_session.execute(text(_SAQ_TABLE))
    await db_session.commit()


async def _insert_job(db_session, key: str, status: str, job_dict: dict):
    """Insert a SAQ-format row (job column = JSON bytes, scheduled = epoch)."""
    import json
    import time

    await _ensure_saq_table(db_session)
    await db_session.execute(
        text(
            """INSERT INTO saq_jobs (key, job, queue, status, scheduled)
            VALUES (:key, CAST(:job AS bytea), 'default', :status, :scheduled)"""
        ).bindparams(job=json.dumps(job_dict).encode("utf-8"), key=key, status=status, scheduled=int(time.time()))
    )
    await db_session.commit()


async def test_jobs_endpoint_includes_failed_status(auth_client, db_session):
    """The /jobs endpoint returns failed rows (recent tail within SAQ retention)."""
    await _insert_job(
        db_session,
        key="failed-1",
        status="failed",
        job_dict={
            "function": "ingest_job",
            "kwargs": {"user_id": 1},
            "attempts": 4,
            "retries": 3,
        },
    )
    resp = await auth_client.get("/api/admin/system/jobs")
    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    failed = [j for j in jobs if j["key"] == "failed-1"]
    assert failed, "failed job row should be visible"
    assert failed[0]["status"] == "failed"
    assert failed[0]["attempts"] == 4


async def test_jobs_endpoint_has_worker_liveness(auth_client):
    resp = await auth_client.get("/api/admin/system/jobs")
    assert resp.status_code == 200
    assert "workers_alive" in resp.json()


async def test_abort_endpoint_aborts_queued_job(auth_client, db_session):
    """Abort of a queued job finishes it as aborted immediately (SAQ semantics)."""
    # Enqueue through SAQ (own connection) so the API's separate pool can see it.
    from saq.queue.postgres import PostgresQueue

    queue = PostgresQueue.from_url("postgresql://test:test@localhost:5433/test", name="default", min_size=1, max_size=2)
    await queue.connect()
    try:
        job = await queue.enqueue("batch_weather_job", user_id=1, group_key="batch_weather", heartbeat=120)
    finally:
        await queue.disconnect()

    resp = await auth_client.post(f"/api/admin/system/jobs/{job.key}/abort")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # verify terminal aborted state
    queue = PostgresQueue.from_url("postgresql://test:test@localhost:5433/test", name="default", min_size=1, max_size=2)
    await queue.connect()
    try:
        fetched = await queue.job(job.key)
        assert fetched is not None and fetched.status.value == "aborted"
    finally:
        await queue.disconnect()


async def test_retry_endpoint_reenqueues_from_dead_letter(auth_client, db_session, seed_user):
    """Retry re-enqueues with the dead-letter event's kwargs under a fresh key."""
    await db_session.execute(
        text(
            """INSERT INTO events (event_type, outcome, user_id, payload)
            VALUES ('job.failed', 'failure', :uid, CAST(:payload AS jsonb))"""
        ).bindparams(
            uid=seed_user.id,
            payload='{"dead_letter": true, "job_name": "ingest", "job_key": "failed-1",'
            ' "kwargs": {"user_id": 1, "fit_bytes_b64": "AAAA", "source": "upload", "source_ref": "a.fit"},'
            ' "attempts": 4, "error": "boom"}',
        )
    )
    await db_session.commit()
    resp = await auth_client.post("/api/admin/system/jobs/failed-1/retry")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


async def test_retry_of_unknown_function_rejected(auth_client):
    """A dead-letter payload for an unknown job function is a 400, not a crash."""
    resp = await auth_client.post("/api/admin/system/jobs/no-such-key/retry")
    assert resp.status_code in (400, 404)


async def test_admin_action_writes_audit_log(auth_client, db_session):
    """Job operations are audited (ADR 0007)."""
    from saq.queue.postgres import PostgresQueue

    queue = PostgresQueue.from_url("postgresql://test:test@localhost:5433/test", name="default", min_size=1, max_size=2)
    await queue.connect()
    try:
        job = await queue.enqueue("flush_cache_stats")
    finally:
        await queue.disconnect()

    resp = await auth_client.post(f"/api/admin/system/jobs/{job.key}/abort")
    assert resp.status_code == 200

    from sqlalchemy import select

    from trainingdash.repositories.postgres.models import AuditLog

    entries = (await db_session.execute(select(AuditLog).where(AuditLog.action == "job.abort"))).scalars().all()
    assert entries
