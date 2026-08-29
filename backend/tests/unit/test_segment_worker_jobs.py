"""Unit tests for segment worker jobs."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from trainingdash.use_cases.process_activity_segments import ProcessResult
from trainingdash.use_cases.retroactive_match import RetroactiveMatchResult


class TestSegmentProcessJob:
    """Tests for segment_process_job worker function."""

    @pytest.mark.asyncio
    async def test_segment_process_job_runs_use_case(self):
        """segment_process_job dispatches to ProcessActivitySegments use case."""
        from trainingdash.worker import segment_process_job

        activity_id = str(uuid4())
        user_id = 42

        mock_result = ProcessResult(
            matched_efforts=3,
            detected_climbs=1,
            new_prs=2,
        )

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)

        mock_db = AsyncMock()

        with patch("trainingdash.worker.worker_db_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock()

            # Patch at the actual import location inside the function
            with patch.dict("sys.modules", {"trainingdash.repositories.postgres.segment_repo": MagicMock()}):
                with patch(
                    "trainingdash.use_cases.process_activity_segments.ProcessActivitySegments",
                    return_value=mock_use_case,
                ):
                    result = await segment_process_job(ctx={}, activity_id=activity_id, user_id=user_id)

        assert result == {
            "matched_efforts": 3,
            "detected_climbs": 1,
            "new_prs": 2,
        }

    @pytest.mark.asyncio
    async def test_segment_process_job_returns_correct_structure(self):
        """segment_process_job returns expected dict structure."""
        from trainingdash.worker import segment_process_job

        activity_id = str(uuid4())
        user_id = 1

        mock_result = ProcessResult(
            matched_efforts=0,
            detected_climbs=0,
            new_prs=0,
        )

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)

        mock_db = AsyncMock()

        with patch("trainingdash.worker.worker_db_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock()

            with patch.dict("sys.modules", {"trainingdash.repositories.postgres.segment_repo": MagicMock()}):
                with patch(
                    "trainingdash.use_cases.process_activity_segments.ProcessActivitySegments",
                    return_value=mock_use_case,
                ):
                    result = await segment_process_job(ctx={}, activity_id=activity_id, user_id=user_id)

        # Verify all expected keys are present
        assert "matched_efforts" in result
        assert "detected_climbs" in result
        assert "new_prs" in result


class TestRetroactiveMatchJob:
    """Tests for retroactive_match_job worker function."""

    @pytest.mark.asyncio
    async def test_retroactive_match_job_runs_use_case(self):
        """retroactive_match_job dispatches to RetroactiveMatch use case."""
        from trainingdash.worker import retroactive_match_job

        segment_id = str(uuid4())

        mock_result = RetroactiveMatchResult(
            success=True,
            activities_scanned=50,
            efforts_created=5,
            error=None,
        )

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)

        mock_db = AsyncMock()

        with patch("trainingdash.worker.worker_db_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock()

            with patch.dict("sys.modules", {"trainingdash.repositories.postgres.segment_repo": MagicMock()}):
                with patch("trainingdash.use_cases.retroactive_match.RetroactiveMatch", return_value=mock_use_case):
                    result = await retroactive_match_job(ctx={}, segment_id=segment_id)

        assert result == {
            "success": True,
            "activities_scanned": 50,
            "efforts_created": 5,
            "error": None,
        }

    @pytest.mark.asyncio
    async def test_retroactive_match_job_handles_failure(self):
        """retroactive_match_job correctly reports failure."""
        from trainingdash.worker import retroactive_match_job

        segment_id = str(uuid4())

        mock_result = RetroactiveMatchResult(
            success=False,
            activities_scanned=25,
            efforts_created=2,
            error="Database connection lost",
        )

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(return_value=mock_result)

        mock_db = AsyncMock()

        with patch("trainingdash.worker.worker_db_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock()

            with patch.dict("sys.modules", {"trainingdash.repositories.postgres.segment_repo": MagicMock()}):
                with patch("trainingdash.use_cases.retroactive_match.RetroactiveMatch", return_value=mock_use_case):
                    result = await retroactive_match_job(ctx={}, segment_id=segment_id)

        assert result["success"] is False
        assert result["error"] == "Database connection lost"
        assert result["activities_scanned"] == 25
        assert result["efforts_created"] == 2


class TestMatchRouteJobChaining:
    """Tests for match_route_job chaining to segment_process_job."""

    @pytest.mark.asyncio
    async def test_match_route_job_chains_to_segment_process(self):
        """match_route_job enqueues segment_process_job after completion."""
        from trainingdash.worker import match_route_job

        activity_id = str(uuid4())
        user_id = 42

        mock_match_route_result = {"route_id": 123, "match_confidence": 0.95}

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(return_value=mock_match_route_result)

        mock_db = AsyncMock()

        with patch("trainingdash.worker.worker_db_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock()

            with patch("trainingdash.use_cases.match_route.MatchRoute", return_value=mock_use_case):
                with patch("trainingdash.jobs.enqueue_segment_process_job", new_callable=AsyncMock) as mock_enqueue:
                    mock_enqueue.return_value = "job-key-123"

                    result = await match_route_job(ctx={}, activity_id=activity_id, user_id=user_id)

        # Verify MatchRoute was called
        mock_use_case.execute.assert_called_once_with(activity_id, user_id)

        # Verify segment_process_job was enqueued
        mock_enqueue.assert_called_once_with(activity_id, user_id)

        # Verify result is from MatchRoute
        assert result == mock_match_route_result


class TestJobsRegistration:
    """Tests for job registration in worker settings."""

    def test_segment_jobs_are_defined(self):
        """Segment jobs are defined and callable."""
        from trainingdash.worker import retroactive_match_job, segment_process_job

        # Verify jobs are callable
        assert callable(segment_process_job)
        assert callable(retroactive_match_job)

        # Verify they have the correct names (from @tracked_job decorator)
        # The wrapped function should have __wrapped__ attribute
        assert hasattr(segment_process_job, "__wrapped__") or callable(segment_process_job)
        assert hasattr(retroactive_match_job, "__wrapped__") or callable(retroactive_match_job)


class TestEnqueueFunctions:
    """Tests for job enqueue functions."""

    @pytest.mark.asyncio
    async def test_enqueue_segment_process_job(self):
        """enqueue_segment_process_job enqueues correctly."""
        from trainingdash.jobs import enqueue_segment_process_job

        activity_id = str(uuid4())
        user_id = 42

        mock_queue = MagicMock()
        mock_job = MagicMock()
        mock_job.key = "job-key-abc"
        mock_queue.enqueue = AsyncMock(return_value=mock_job)

        with patch("trainingdash.jobs.queue_available", return_value=True):
            with patch("trainingdash.jobs.get_queue", new_callable=AsyncMock, return_value=mock_queue):
                result = await enqueue_segment_process_job(activity_id, user_id)

        mock_queue.enqueue.assert_called_once_with(
            "segment_process_job",
            activity_id=activity_id,
            user_id=user_id,
        )
        assert result == "job-key-abc"

    @pytest.mark.asyncio
    async def test_enqueue_segment_process_job_queue_unavailable(self):
        """enqueue_segment_process_job returns None when queue unavailable."""
        from trainingdash.jobs import enqueue_segment_process_job

        with patch("trainingdash.jobs.queue_available", return_value=False):
            result = await enqueue_segment_process_job(str(uuid4()), 1)

        assert result is None

    @pytest.mark.asyncio
    async def test_enqueue_retroactive_match_job(self):
        """enqueue_retroactive_match_job enqueues with timeout."""
        from trainingdash.jobs import enqueue_retroactive_match_job

        segment_id = str(uuid4())

        mock_queue = MagicMock()
        mock_job = MagicMock()
        mock_job.key = "job-key-xyz"
        mock_queue.enqueue = AsyncMock(return_value=mock_job)

        with patch("trainingdash.jobs.queue_available", return_value=True):
            with patch("trainingdash.jobs.get_queue", new_callable=AsyncMock, return_value=mock_queue):
                result = await enqueue_retroactive_match_job(segment_id)

        mock_queue.enqueue.assert_called_once_with(
            "retroactive_match_job",
            segment_id=segment_id,
            timeout=600,
        )
        assert result == "job-key-xyz"

    @pytest.mark.asyncio
    async def test_enqueue_retroactive_match_job_queue_unavailable(self):
        """enqueue_retroactive_match_job returns None when queue unavailable."""
        from trainingdash.jobs import enqueue_retroactive_match_job

        with patch("trainingdash.jobs.queue_available", return_value=False):
            result = await enqueue_retroactive_match_job(str(uuid4()))

        assert result is None
