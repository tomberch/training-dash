"""Tests for suggestion visibility — the 3+ repetition threshold.

CONTEXT.md: suggestions are proposed to users who have ridden a segment
"3+ times". The listing endpoints only return suggestions whose
repetition_count has reached that threshold.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from tests.fakes.segment_repos import FakeSegmentSuggestionRepo
from trainingdash.repositories.postgres.models import SegmentSuggestion


def make_suggestion(user_id: int, repetition_count: int) -> SegmentSuggestion:
    now = datetime.now()
    return SegmentSuggestion(
        id=uuid4(),
        segment_id=uuid4(),
        user_id=user_id,
        repetition_count=repetition_count,
        first_ridden_at=now,
        last_ridden_at=now,
        expires_at=now + timedelta(days=90),
    )


class TestSuggestionVisibilityThreshold:
    @pytest.mark.asyncio
    async def test_list_for_user_returns_only_three_plus(self):
        repo = FakeSegmentSuggestionRepo()
        repo.add(make_suggestion(user_id=1, repetition_count=1))
        repo.add(make_suggestion(user_id=1, repetition_count=2))
        repo.add(make_suggestion(user_id=1, repetition_count=3))
        repo.add(make_suggestion(user_id=1, repetition_count=5))

        visible = await repo.list_for_user(user_id=1)

        assert [s.repetition_count for s in visible] == [5, 3]

    @pytest.mark.asyncio
    async def test_count_for_user_respects_threshold(self):
        repo = FakeSegmentSuggestionRepo()
        repo.add(make_suggestion(user_id=1, repetition_count=1))
        repo.add(make_suggestion(user_id=1, repetition_count=2))
        repo.add(make_suggestion(user_id=1, repetition_count=4))

        assert await repo.count_for_user(user_id=1) == 1

    @pytest.mark.asyncio
    async def test_dismissed_suggestions_still_excluded(self):
        repo = FakeSegmentSuggestionRepo()
        dismissed = make_suggestion(user_id=1, repetition_count=7)
        dismissed.dismissed_at = datetime.now()
        repo.add(dismissed)
        repo.add(make_suggestion(user_id=1, repetition_count=3))

        visible = await repo.list_for_user(user_id=1)

        assert [s.repetition_count for s in visible] == [3]

    @pytest.mark.asyncio
    async def test_dismiss_all_only_dismisses_visible(self):
        """Dismiss-all must not touch below-threshold suggestions the user
        has never seen — the confirm dialog quotes the visible total."""
        repo = FakeSegmentSuggestionRepo()
        repo.add(make_suggestion(user_id=1, repetition_count=1))
        repo.add(make_suggestion(user_id=1, repetition_count=2))
        repo.add(make_suggestion(user_id=1, repetition_count=5))

        dismissed = await repo.dismiss_all(user_id=1)

        assert dismissed == 1  # only the visible one
        # The two below-threshold suggestions are untouched
        untouched = [s for s in repo.all() if s.dismissed_at is None]
        assert len(untouched) == 2
        assert {s.repetition_count for s in untouched} == {1, 2}

    @pytest.mark.asyncio
    async def test_expired_suggestions_not_shown(self):
        """CONTEXT.md: suggestions expire 90 days after the last ride."""
        repo = FakeSegmentSuggestionRepo()
        expired = make_suggestion(user_id=1, repetition_count=9)
        expired.expires_at = datetime.now() - timedelta(days=1)
        repo.add(expired)
        repo.add(make_suggestion(user_id=1, repetition_count=4))

        visible = await repo.list_for_user(user_id=1)

        assert [s.repetition_count for s in visible] == [4]
        assert await repo.count_for_user(user_id=1) == 1

    @pytest.mark.asyncio
    async def test_dismiss_all_skips_expired(self):
        repo = FakeSegmentSuggestionRepo()
        expired = make_suggestion(user_id=1, repetition_count=9)
        expired.expires_at = datetime.now() - timedelta(days=1)
        repo.add(expired)
        repo.add(make_suggestion(user_id=1, repetition_count=4))

        dismissed = await repo.dismiss_all(user_id=1)

        assert dismissed == 1

    @pytest.mark.asyncio
    async def test_other_users_suggestions_not_mixed_in(self):
        repo = FakeSegmentSuggestionRepo()
        repo.add(make_suggestion(user_id=2, repetition_count=9))
        repo.add(make_suggestion(user_id=1, repetition_count=3))

        visible = await repo.list_for_user(user_id=1)

        assert all(s.user_id == 1 for s in visible)
