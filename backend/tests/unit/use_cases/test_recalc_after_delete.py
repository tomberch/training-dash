"""Unit tests for RecalcAfterDelete use case."""

from unittest import mock

import pytest

from trainingdash.use_cases.recalc_after_delete import RecalcAfterDelete


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = mock.AsyncMock()
    session.commit = mock.AsyncMock()
    return session


@pytest.fixture
def use_case(mock_db_session):
    return RecalcAfterDelete(mock_db_session)


class TestRecalcAfterDelete:
    """Tests for RecalcAfterDelete use case."""

    @pytest.mark.asyncio
    async def test_executes_fitness_model_updater(self, use_case, mock_db_session):
        """Should execute FitnessModelUpdater."""
        with (
            mock.patch("trainingdash.use_cases.recalc_after_delete.FitnessModelUpdater") as MockFMU,
            mock.patch("trainingdash.use_cases.recalc_after_delete.BreakthroughEvaluator") as MockBE,
        ):
            MockFMU.return_value.execute = mock.AsyncMock()
            MockBE.return_value.execute = mock.AsyncMock()

            result = await use_case.execute(user_id=1)

            MockFMU.assert_called_once_with(mock_db_session)
            MockFMU.return_value.execute.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_executes_breakthrough_evaluator(self, use_case, mock_db_session):
        """Should execute BreakthroughEvaluator."""
        with (
            mock.patch("trainingdash.use_cases.recalc_after_delete.FitnessModelUpdater") as MockFMU,
            mock.patch("trainingdash.use_cases.recalc_after_delete.BreakthroughEvaluator") as MockBE,
        ):
            MockFMU.return_value.execute = mock.AsyncMock()
            MockBE.return_value.execute = mock.AsyncMock()

            result = await use_case.execute(user_id=1)

            MockBE.assert_called_once_with(mock_db_session)
            MockBE.return_value.execute.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_commits_after_each_step(self, use_case, mock_db_session):
        """Should commit after each step."""
        with (
            mock.patch("trainingdash.use_cases.recalc_after_delete.FitnessModelUpdater") as MockFMU,
            mock.patch("trainingdash.use_cases.recalc_after_delete.BreakthroughEvaluator") as MockBE,
        ):
            MockFMU.return_value.execute = mock.AsyncMock()
            MockBE.return_value.execute = mock.AsyncMock()

            await use_case.execute(user_id=1)

            # Should commit twice: once after FMU, once after BE
            assert mock_db_session.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_success_dict(self, use_case, mock_db_session):
        """Should return success dict with user_id."""
        with (
            mock.patch("trainingdash.use_cases.recalc_after_delete.FitnessModelUpdater") as MockFMU,
            mock.patch("trainingdash.use_cases.recalc_after_delete.BreakthroughEvaluator") as MockBE,
        ):
            MockFMU.return_value.execute = mock.AsyncMock()
            MockBE.return_value.execute = mock.AsyncMock()

            result = await use_case.execute(user_id=42)

            assert result == {"success": True, "user_id": 42}

    @pytest.mark.asyncio
    async def test_continues_on_fitness_model_failure(self, use_case, mock_db_session):
        """Should continue to breakthrough evaluator even if fitness model fails."""
        with (
            mock.patch("trainingdash.use_cases.recalc_after_delete.FitnessModelUpdater") as MockFMU,
            mock.patch("trainingdash.use_cases.recalc_after_delete.BreakthroughEvaluator") as MockBE,
        ):
            MockFMU.return_value.execute = mock.AsyncMock(side_effect=Exception("FMU error"))
            MockBE.return_value.execute = mock.AsyncMock()

            result = await use_case.execute(user_id=1)

            # Should still call breakthrough evaluator
            MockBE.return_value.execute.assert_called_once_with(1)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_continues_on_breakthrough_evaluator_failure(self, use_case, mock_db_session):
        """Should return success even if breakthrough evaluator fails."""
        with (
            mock.patch("trainingdash.use_cases.recalc_after_delete.FitnessModelUpdater") as MockFMU,
            mock.patch("trainingdash.use_cases.recalc_after_delete.BreakthroughEvaluator") as MockBE,
        ):
            MockFMU.return_value.execute = mock.AsyncMock()
            MockBE.return_value.execute = mock.AsyncMock(side_effect=Exception("BE error"))

            result = await use_case.execute(user_id=1)

            # Should still return success (idempotent)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_both_steps_fail_still_returns_success(self, use_case, mock_db_session):
        """Should return success even if both steps fail (idempotent)."""
        with (
            mock.patch("trainingdash.use_cases.recalc_after_delete.FitnessModelUpdater") as MockFMU,
            mock.patch("trainingdash.use_cases.recalc_after_delete.BreakthroughEvaluator") as MockBE,
        ):
            MockFMU.return_value.execute = mock.AsyncMock(side_effect=Exception("FMU error"))
            MockBE.return_value.execute = mock.AsyncMock(side_effect=Exception("BE error"))

            result = await use_case.execute(user_id=1)

            assert result == {"success": True, "user_id": 1}
