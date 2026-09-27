"""Tests for HourlyImportScheduler lost-tick safeguard (ADR 0006, decision 3).

When the scheduler sees a scheduled user whose last_synced_at is >25h stale,
it writes a sync.lost_tick event (visibility for the admin surface, ADR 0007).
Also verifies hour-bucketed dedup keys are passed to enqueue helpers (ADR 0006 D1).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trainingdash.use_cases.hourly_import_scheduler import HourlyImportScheduler


def _user_row(user_id: int):
    row = MagicMock()
    row.user_id = user_id
    return row


def _cred_row(user_id: int, hours_since_sync: float | None):
    row = MagicMock()
    row.user_id = user_id
    if hours_since_sync is None:
        row.last_synced_at = None
    else:
        row.last_synced_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours_since_sync)
    return row


@pytest.fixture
def scheduler_env():
    """Scheduler with mocked queries, enqueue helpers, and event repo."""
    event_repo = MagicMock()
    event_repo.log = AsyncMock()

    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    scheduler = HourlyImportScheduler(db)
    scheduler._event_repo = event_repo

    return scheduler, db, event_repo


async def _run(scheduler, db, garmin_ids, garmin_creds, xert_ids, xert_creds):
    def _result(ids):
        r = MagicMock()
        r.scalars.return_value.all.return_value = ids
        return r

    stale_rows = [(c.user_id, c.last_synced_at) for c in garmin_creds + xert_creds]

    def _result(ids, rows=None):
        r = MagicMock()
        r.scalars.return_value.all.return_value = ids
        r.all.return_value = rows if rows is not None else []
        return r

    db.execute = AsyncMock(
        side_effect=[
            _result(garmin_ids),
            _result(xert_ids),
            _result([], rows=stale_rows),
        ]
    )

    with patch(
        "trainingdash.use_cases.hourly_import_scheduler.enqueue_import_garmin_job", new_callable=AsyncMock
    ) as garmin_enq:
        with patch(
            "trainingdash.use_cases.hourly_import_scheduler.enqueue_import_xert_job", new_callable=AsyncMock
        ) as xert_enq:
            result = await scheduler.execute()
    return result, garmin_enq, xert_enq


async def test_lost_tick_event_when_last_sync_older_than_25h(scheduler_env):
    scheduler, db, event_repo = scheduler_env
    # user 7 scheduled, but last synced 30h ago (missed ticks / worker down)
    result, garmin_enq, xert_enq = await _run(
        scheduler, db,
        garmin_ids=[_user_row(7)], garmin_creds=[_cred_row(7, hours_since_sync=30)],
        xert_ids=[], xert_creds=[],
    )

    assert result["success"] is True
    lost = [c for c in event_repo.log.call_args_list if c.kwargs["event_type"] == "sync.lost_tick"]
    assert len(lost) == 1
    assert lost[0].kwargs["user_id"] == 7


async def test_no_lost_tick_when_synced_recently(scheduler_env):
    scheduler, db, event_repo = scheduler_env
    result, garmin_enq, xert_enq = await _run(
        scheduler, db,
        garmin_ids=[_user_row(7)], garmin_creds=[_cred_row(7, hours_since_sync=1)],
        xert_ids=[], xert_creds=[],
    )

    lost = [c for c in event_repo.log.call_args_list if c.kwargs["event_type"] == "sync.lost_tick"]
    assert lost == []


async def test_hour_bucketed_keys_passed_to_enqueues(scheduler_env):
    """Scheduler passes hour-bucketed keys so retried ticks dedupe (ADR 0006 D1)."""
    scheduler, db, event_repo = scheduler_env
    result, garmin_enq, xert_enq = await _run(
        scheduler, db,
        garmin_ids=[_user_row(5)], garmin_creds=[_cred_row(5, hours_since_sync=1)],
        xert_ids=[_user_row(9)], xert_creds=[_cred_row(9, hours_since_sync=1)],
    )

    assert result["garmin_queued"] == 1
    assert result["xert_queued"] == 1

    garmin_kwargs = garmin_enq.call_args.kwargs
    assert "garmin" in garmin_kwargs.get("key", "")
    assert str(garmin_enq.call_args.args[0] if garmin_enq.call_args.args else garmin_enq.call_args.kwargs.get("user_id")) in garmin_kwargs.get("key", "")
    # Key contains an hour bucket (YYYY-MM-DDTHH fragment)
    assert f"T{datetime.now(UTC).hour:02d}" in garmin_kwargs["key"]

    xert_kwargs = xert_enq.call_args.kwargs
    assert "xert" in xert_kwargs.get("key", "")
    assert f"T{datetime.now(UTC).hour:02d}" in xert_kwargs["key"]