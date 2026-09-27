"""Tests for the three-class enqueue-failure call-site policy (ADR 0006, decision 3 / ticket #689).

Class A (user-facing API): enqueue failure → 503 (upload keeps sync fallback).
Class B (internal chains): failure → job.enqueue_failed event (+ user Notification when
    an identifiable user is affected); never raises past the endpoint.
Class C (recalculation): both None and EnqueueError mark the recalculation_jobs row failed
    (fixes the stranded-pending bug).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from trainingdash.jobs import EnqueueError


# ---------------------------------------------------------------------------
# Class A — user-facing API endpoints surface 503
# ---------------------------------------------------------------------------


async def test_user_import_trigger_503_on_enqueue_error():
    """POST /me/import/* must 503 when enqueue fails with EnqueueError."""
    from trainingdash.routers.user import trigger_xert_import

    creds_repo = MagicMock()
    creds_repo.get_by_user_id = AsyncMock(
        return_value=MagicMock(sync_enabled=True)
    )

    with patch(
        "trainingdash.jobs.enqueue_import_xert_job",
        new_callable=AsyncMock,
        side_effect=EnqueueError("pool exhausted"),
    ):
        with pytest.raises(HTTPException) as exc:
            await trigger_xert_import(creds_repo, user=MagicMock(id=1))

    assert exc.value.status_code == 503


async def test_user_import_trigger_503_on_none():
    """None (queue unavailable) is also a 503 on user-facing endpoints."""
    from trainingdash.routers.user import trigger_garmin_import

    creds_repo = MagicMock()
    creds_repo.get_by_user_id = AsyncMock(return_value=MagicMock(sync_enabled=True))

    with patch("trainingdash.jobs.enqueue_import_garmin_job", new_callable=AsyncMock, return_value=None):
        with pytest.raises(HTTPException) as exc:
            await trigger_garmin_import(creds_repo, user=MagicMock(id=1))

    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# Class B — internal chains record events, never raise
# ---------------------------------------------------------------------------


async def test_delete_activity_enqueue_failure_writes_event_not_raises():
    """recalc-after-delete chain: EnqueueError → job.enqueue_failed event; deletion still succeeds."""
    from trainingdash.use_cases.delete_activity import DeleteActivity

    db = MagicMock()
    db.commit = AsyncMock()

    event_repo = MagicMock()
    event_repo.log = AsyncMock()

    activity = MagicMock()
    activity.id = "act-1"
    activity.route = None

    segment_repo = MagicMock()
    activity_repo = MagicMock()
    activity_repo.get_owned = AsyncMock(return_value=activity)
    activity_repo.delete = AsyncMock(return_value=True)

    use_case = DeleteActivity(activity_repo=activity_repo, segment_repo=segment_repo, event_repo=event_repo)

    with patch(
        "trainingdash.jobs.enqueue_recalculate_after_delete_job",
        new_callable=AsyncMock,
        side_effect=EnqueueError("queue down"),
    ):
        result = await use_case.execute(user_id=7, activity_id="a1")

    assert result is True
    # an enqueue-failed event was recorded
    types = [c.kwargs["event_type"] for c in event_repo.log.call_args_list]
    assert "job.enqueue_failed" in types


async def test_delete_activity_enqueue_none_writes_event():
    """None (dev no-queue) on an internal chain also records the lost follow-up."""
    from trainingdash.use_cases.delete_activity import DeleteActivity

    event_repo = MagicMock()
    event_repo.log = AsyncMock()
    activity_repo = MagicMock()
    activity_repo.get_owned = AsyncMock(return_value=MagicMock(id="a1", route=None))
    activity_repo.delete = AsyncMock(return_value=True)

    use_case = DeleteActivity(activity_repo=activity_repo, segment_repo=MagicMock(), event_repo=event_repo)

    with patch("trainingdash.jobs.enqueue_recalculate_after_delete_job", new_callable=AsyncMock, return_value=None):
        result = await use_case.execute(user_id=7, activity_id="a1")

    assert result is True
    types = [c.kwargs["event_type"] for c in event_repo.log.call_args_list]
    assert "job.enqueue_failed" in types


# ---------------------------------------------------------------------------
# Class C — recalculation paths fix the stranded-pending bug
# ---------------------------------------------------------------------------


async def test_recalc_enqueue_failure_marks_job_failed():
    """Threshold save: EnqueueError must mark the recalculation_jobs row failed (not stranded pending)."""
    # The route handler catches EnqueueError like any Exception and marks failed.
    # This test pins the behavior at the seam the route uses.
    from trainingdash.routers.user import _enqueue_recalc_or_fail  # helper to be added

    recalc_repo = MagicMock()
    recalc_repo.mark_failed = AsyncMock()

    await _enqueue_recalc_or_fail(
        user_id=7,
        recalc_repo=recalc_repo,
        enqueue=AsyncMock(side_effect=EnqueueError("pool exhausted")),
    )

    recalc_repo.mark_failed.assert_awaited_once_with(7, "Failed to enqueue job. Please try again.")


async def test_recalc_enqueue_none_also_marks_failed():
    """None (queue unavailable) previously stranded the pending row — must mark failed too."""
    from trainingdash.routers.user import _enqueue_recalc_or_fail

    recalc_repo = MagicMock()
    recalc_repo.mark_failed = AsyncMock()

    await _enqueue_recalc_or_fail(
        user_id=7,
        recalc_repo=recalc_repo,
        enqueue=AsyncMock(return_value=None),
    )

    recalc_repo.mark_failed.assert_awaited_once_with(7, "Failed to enqueue job. Please try again.")


async def test_recalc_enqueue_success_does_not_mark_failed():
    from trainingdash.routers.user import _enqueue_recalc_or_fail

    recalc_repo = MagicMock()
    recalc_repo.mark_failed = AsyncMock()

    await _enqueue_recalc_or_fail(
        user_id=7,
        recalc_repo=recalc_repo,
        enqueue=AsyncMock(return_value="job-key"),
    )

    recalc_repo.mark_failed.assert_not_awaited()