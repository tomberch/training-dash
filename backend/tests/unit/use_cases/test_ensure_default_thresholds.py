"""Unit tests for EnsureDefaultThresholds use case."""

from datetime import date
from unittest import mock

import pytest

from trainingdash.use_cases.ensure_default_thresholds import EnsureDefaultThresholds


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = mock.AsyncMock()
    session.commit = mock.AsyncMock()
    return session


@pytest.fixture
def mock_threshold_repo():
    """Create a mock threshold repository."""
    repo = mock.AsyncMock()
    repo.has_any_threshold = mock.AsyncMock(return_value=False)
    repo.create = mock.AsyncMock()
    return repo


@pytest.fixture
def use_case(mock_db_session, mock_threshold_repo):
    uc = EnsureDefaultThresholds(mock_db_session)
    uc._repo = mock_threshold_repo
    return uc


class TestEnsureDefaultThresholds:
    """Tests for EnsureDefaultThresholds use case."""

    @pytest.mark.asyncio
    async def test_returns_false_when_dob_is_none(self, use_case, mock_threshold_repo):
        """Should return False immediately when dob is None."""
        result = await use_case.execute(user_id=1, dob=None, weight_kg=75.0)

        assert result is False
        mock_threshold_repo.has_any_threshold.assert_not_called()
        mock_threshold_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_thresholds_exist(
        self, use_case, mock_threshold_repo
    ):
        """Should return False when user already has thresholds."""
        mock_threshold_repo.has_any_threshold.return_value = True

        result = await use_case.execute(
            user_id=1, dob=date(1990, 1, 1), weight_kg=75.0
        )

        assert result is False
        mock_threshold_repo.has_any_threshold.assert_called_once_with(1)
        mock_threshold_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_defaults_when_no_thresholds(
        self, use_case, mock_db_session, mock_threshold_repo
    ):
        """Should create default thresholds when none exist."""
        mock_threshold_repo.has_any_threshold.return_value = False

        result = await use_case.execute(
            user_id=1, dob=date(1990, 1, 1), weight_kg=75.0
        )

        assert result is True
        mock_threshold_repo.create.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_defaults_with_correct_source(
        self, use_case, mock_threshold_repo
    ):
        """Should create thresholds with 'calculated' source."""
        mock_threshold_repo.has_any_threshold.return_value = False

        await use_case.execute(user_id=1, dob=date(1990, 1, 1), weight_kg=75.0)

        # Check the create call arguments
        call_kwargs = mock_threshold_repo.create.call_args.kwargs
        assert call_kwargs["source"] == "calculated"
        assert call_kwargs["source_detail"] == "default_from_age_weight"

    @pytest.mark.asyncio
    async def test_uses_computed_threshold_values(
        self, use_case, mock_threshold_repo
    ):
        """Should use values from compute_default_thresholds."""
        mock_threshold_repo.has_any_threshold.return_value = False

        with mock.patch(
            "trainingdash.use_cases.ensure_default_thresholds.compute_default_thresholds"
        ) as mock_compute:
            mock_compute.return_value = {
                "ftp_watts": 200,
                "lthr_bpm": 165,
                "hrmax_bpm": 185,
            }

            await use_case.execute(user_id=1, dob=date(1990, 1, 1), weight_kg=75.0)

            mock_compute.assert_called_once_with(date(1990, 1, 1), 75.0)
            call_kwargs = mock_threshold_repo.create.call_args.kwargs
            assert call_kwargs["ftp_watts"] == 200
            assert call_kwargs["lthr_bpm"] == 165
            assert call_kwargs["hrmax_bpm"] == 185

    @pytest.mark.asyncio
    async def test_creates_thresholds_with_today_date(
        self, use_case, mock_threshold_repo
    ):
        """Should create threshold entry dated today."""
        mock_threshold_repo.has_any_threshold.return_value = False

        await use_case.execute(user_id=1, dob=date(1990, 1, 1), weight_kg=75.0)

        call_args = mock_threshold_repo.create.call_args.args
        # Second positional arg should be today's date
        assert call_args[1] == date.today()

    @pytest.mark.asyncio
    async def test_works_without_weight(self, use_case, mock_threshold_repo):
        """Should create defaults even when weight is None."""
        mock_threshold_repo.has_any_threshold.return_value = False

        result = await use_case.execute(
            user_id=1, dob=date(1990, 1, 1), weight_kg=None
        )

        assert result is True
        mock_threshold_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_user_id_to_repo(self, use_case, mock_threshold_repo):
        """Should pass correct user_id to repository methods."""
        mock_threshold_repo.has_any_threshold.return_value = False

        await use_case.execute(user_id=42, dob=date(1990, 1, 1), weight_kg=75.0)

        mock_threshold_repo.has_any_threshold.assert_called_with(42)
        call_args = mock_threshold_repo.create.call_args.args
        assert call_args[0] == 42  # First positional arg is user_id


class TestEnsureDefaultThresholdsIdempotency:
    """Tests for idempotency of EnsureDefaultThresholds."""

    @pytest.mark.asyncio
    async def test_idempotent_multiple_calls(self, mock_db_session):
        """Should be safe to call multiple times."""
        use_case = EnsureDefaultThresholds(mock_db_session)

        mock_repo = mock.AsyncMock()
        # First call: no thresholds
        mock_repo.has_any_threshold.side_effect = [False, True]
        mock_repo.create = mock.AsyncMock()
        use_case._repo = mock_repo

        # First call creates
        result1 = await use_case.execute(
            user_id=1, dob=date(1990, 1, 1), weight_kg=75.0
        )
        # Second call finds existing
        result2 = await use_case.execute(
            user_id=1, dob=date(1990, 1, 1), weight_kg=75.0
        )

        assert result1 is True
        assert result2 is False
        assert mock_repo.create.call_count == 1
