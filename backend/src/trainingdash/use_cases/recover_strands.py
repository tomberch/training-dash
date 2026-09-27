"""
RecoverStrands use case — strand-recovery cron (ADR 0006, decision 2).

SAQ's sweeper recovers orphaned saq_jobs rows, but our app-level status tables
are stranded when a worker dies mid-job: a ``recalculation_jobs`` row stuck in
``running`` leaves the user's UI in eternal "processing", and a ``BackupHistory``
row stuck in ``running`` blocks all future scheduled backups
(``is_backup_running`` guard). This hourly cron marks such rows failed.

Grace periods: ~2× each job's timeout (recalc 300s → 600s; backup 1800s → 3600s).
"""

import logging
from typing import Any

from trainingdash.domain.events import EventOutcome, EventType

logger = logging.getLogger(__name__)


class RecoverStrands:
    """Mark app-level status rows failed when their worker died mid-run."""

    def __init__(self, recalculation_job_repo, backup_repo, event_repo=None):
        self._recalc_repo = recalculation_job_repo
        self._backup_repo = backup_repo
        self._event_repo = event_repo

    async def execute(self) -> dict:
        recalc_recovered = await self._recalc_repo.recover_stranded_running(
            grace_seconds=600,
            error_message="stuck — recovered by sweeper",
        )
        backup_recovered = await self._backup_repo.recover_stranded_running(
            grace_seconds=3600,
            error_message="backup stuck — recovered by sweeper",
        )

        for event in recalc_recovered + backup_recovered:
            await self._log_strand_event(event)

        return {
            "recalculation_recovered": len(recalc_recovered),
            "backup_recovered": len(backup_recovered),
        }

    async def _log_strand_event(self, event: dict[str, Any]) -> None:
        if self._event_repo is None:
            return
        try:
            await self._event_repo.log(
                event_type=EventType.JOB_STUCK.value,
                outcome=EventOutcome.INFO.value,
                user_id=event.get("user_id"),
                payload=event,
            )
        except Exception:
            logger.exception("Failed to log strand-recovery event")