"""Tests for the strand-recovery cron (ADR 0006, decision 2).

RecoverStrands marks app-level status rows failed when their worker died
mid-run: recalculation_jobs stuck in 'running' past a grace period, and
BackupHistory rows stuck in 'running'. Repos expose recover_stranded_running().
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from trainingdash.use_cases.recover_strands import RecoverStrands


def _repo(recovered: list[dict]):
    repo = MagicMock()
    repo.recover_stranded_running = AsyncMock(return_value=recovered)
    return repo


async def test_recalc_and_backup_strands_recovered():
    recalc_repo = _repo([{"user_id": 7, "table": "recalculation_jobs"}])
    backup_repo = _repo([{"history_id": 3, "table": "backup_history"}])

    result = await RecoverStrands(recalculation_job_repo=recalc_repo, backup_repo=backup_repo).execute()

    assert result == {"recalculation_recovered": 1, "backup_recovered": 1}
    recalc_repo.recover_stranded_running.assert_called_once_with(
        grace_seconds=600, error_message="stuck — recovered by sweeper"
    )
    backup_repo.recover_stranded_running.assert_called_once_with(
        grace_seconds=3600,
        error_message="backup stuck — recovered by sweeper",
    )


async def test_grace_periods_are_2x_timeouts():
    recalc_repo = _repo([])
    backup_repo = _repo([])

    await RecoverStrands(recalculation_job_repo=recalc_repo, backup_repo=backup_repo).execute()

    assert recalc_repo.recover_stranded_running.call_args.kwargs["grace_seconds"] == 600
    assert backup_repo.recover_stranded_running.call_args.kwargs["grace_seconds"] == 3600


async def test_events_written_for_recovered_strands():
    event_repo = MagicMock()
    event_repo.log = AsyncMock()
    recalc_repo = _repo([{"user_id": 7, "table": "recalculation_jobs"}])
    backup_repo = _repo([])

    await RecoverStrands(
        recalculation_job_repo=recalc_repo, backup_repo=backup_repo, event_repo=event_repo
    ).execute()

    calls = event_repo.log.call_args_list
    assert len(calls) == 1
    assert calls[0].kwargs["event_type"] == "job.stuck"
    assert calls[0].kwargs["user_id"] == 7


async def test_no_strands_no_events():
    event_repo = MagicMock()
    event_repo.log = AsyncMock()

    result = await RecoverStrands(
        recalculation_job_repo=_repo([]), backup_repo=_repo([]), event_repo=event_repo
    ).execute()

    assert result == {"recalculation_recovered": 0, "backup_recovered": 0}
    event_repo.log.assert_not_called()


async def test_event_repo_failure_does_not_break_recovery():
    event_repo = MagicMock()
    event_repo.log = AsyncMock(side_effect=RuntimeError("db write failed"))

    result = await RecoverStrands(
        recalculation_job_repo=_repo([{"user_id": 7, "table": "recalculation_jobs"}]),
        backup_repo=_repo([]),
        event_repo=event_repo,
    ).execute()

    assert result["recalculation_recovered"] == 1