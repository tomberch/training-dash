"""Integration tests for recover_stranded_running on the recalc + backup repos.

The strand-recovery cron (ADR 0006, decision 2) calls these to mark
app-level rows failed when their worker died mid-run.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from trainingdash.repositories.postgres.backup_repo import PostgresBackupRepo
from trainingdash.repositories.postgres.models import BackupHistory, RecalculationJob
from trainingdash.repositories.postgres.recalculation_job_repo import PostgresRecalculationJobRepo


def _naive(minutes_ago: int) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=minutes_ago)


async def test_recalc_recover_stranded_running(db_session, seed_user):
    repo = PostgresRecalculationJobRepo(db_session)
    user_id = seed_user.id

    await repo.mark_running(user_id)
    # Age the row past the 600s grace period
    result = await db_session.execute(select(RecalculationJob).where(RecalculationJob.user_id == user_id))
    row = result.scalars().one()
    row.started_at = _naive(minutes_ago=30)
    await db_session.commit()

    recovered = await repo.recover_stranded_running(grace_seconds=600, error_message="stuck — recovered by sweeper")

    assert len(recovered) == 1
    assert recovered[0]["user_id"] == user_id

    job = await repo.get_by_user_id(user_id)
    assert job.status == "failed"
    assert "recovered by sweeper" in job.error_message


async def test_recalc_recent_running_row_not_recovered(db_session, seed_user):
    repo = PostgresRecalculationJobRepo(db_session)
    user_id = seed_user.id

    await repo.mark_running(user_id)  # started_at = now

    recovered = await repo.recover_stranded_running(grace_seconds=600, error_message="x")

    assert recovered == []
    job = await repo.get_by_user_id(user_id)
    assert job.status == "running"


async def test_backup_recover_stranded_running(db_session):
    repo = PostgresBackupRepo(db_session)
    history = await repo.create_history_entry(
        trigger_type="scheduled",
        status="running",
    )
    result = await db_session.execute(select(BackupHistory).where(BackupHistory.id == history.id))
    row = result.scalars().one()
    row.started_at = _naive(minutes_ago=90)
    await db_session.flush()

    recovered = await repo.recover_stranded_running(grace_seconds=3600, error_message="backup stuck")

    assert len(recovered) == 1
    entry = await repo.get_history_entry(history.id)
    assert entry.status == "failed"
    assert "recovered by sweeper" in (entry.error_message or "") or entry.error_message == "backup stuck"