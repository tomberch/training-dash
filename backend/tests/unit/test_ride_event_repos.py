"""
Unit tests for RideEvent fake repositories.

Tests demonstrate usage patterns and verify fake implementations
match the expected protocol behavior.
"""

from datetime import date
from uuid import uuid4

import pytest

from tests.fakes import (
    FakeJournalEntryActivityRepo,
    FakeJournalEntryRepo,
    FakeRideEventLinkRepo,
    FakeRideEventMediaRepo,
    FakeRideEventRepo,
)
from trainingdash.repositories.postgres.models import (
    JournalEntry,
    RideEvent,
    RideEventLink,
    RideEventMedia,
)


class TestFakeRideEventRepo:
    """Tests for FakeRideEventRepo."""

    @pytest.fixture
    def repo(self):
        return FakeRideEventRepo()

    async def test_save_and_get_event(self, repo: FakeRideEventRepo):
        event_id = uuid4()
        event = RideEvent(
            id=event_id,
            user_id=1,
            title="Alps Tour 2026",
            event_type="multi_day",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 7),
        )

        saved = await repo.save(event)
        assert saved.id == event_id

        found = await repo.get_by_id(event_id, user_id=1)
        assert found is not None
        assert found.title == "Alps Tour 2026"
        assert found.event_type == "multi_day"

    async def test_get_returns_none_for_wrong_user(self, repo: FakeRideEventRepo):
        event_id = uuid4()
        event = RideEvent(
            id=event_id,
            user_id=1,
            title="My Event",
            event_type="race",
            start_date=date(2026, 8, 15),
        )
        await repo.save(event)

        # Different user can't access
        found = await repo.get_by_id(event_id, user_id=2)
        assert found is None

    async def test_list_for_user_returns_sorted_by_date(self, repo: FakeRideEventRepo):
        # Create events with different start dates
        event1 = RideEvent(
            id=uuid4(),
            user_id=1,
            title="January Race",
            event_type="race",
            start_date=date(2026, 1, 15),
        )
        event2 = RideEvent(
            id=uuid4(),
            user_id=1,
            title="March Tour",
            event_type="multi_day",
            start_date=date(2026, 3, 1),
        )
        event3 = RideEvent(
            id=uuid4(),
            user_id=1,
            title="February Fondo",
            event_type="gran_fondo",
            start_date=date(2026, 2, 10),
        )

        await repo.save(event1)
        await repo.save(event2)
        await repo.save(event3)

        events = await repo.list_for_user(user_id=1)
        assert len(events) == 3
        # Should be sorted by start_date descending (newest first)
        assert events[0].title == "March Tour"
        assert events[1].title == "February Fondo"
        assert events[2].title == "January Race"

    async def test_list_filters_by_event_type(self, repo: FakeRideEventRepo):
        await repo.save(
            RideEvent(id=uuid4(), user_id=1, title="Race 1", event_type="race", start_date=date(2026, 1, 1))
        )
        await repo.save(
            RideEvent(id=uuid4(), user_id=1, title="Tour 1", event_type="multi_day", start_date=date(2026, 2, 1))
        )
        await repo.save(
            RideEvent(id=uuid4(), user_id=1, title="Race 2", event_type="race", start_date=date(2026, 3, 1))
        )

        races = await repo.list_for_user(user_id=1, event_type="race")
        assert len(races) == 2
        assert all(e.event_type == "race" for e in races)

    async def test_list_pagination(self, repo: FakeRideEventRepo):
        for i in range(5):
            await repo.save(
                RideEvent(
                    id=uuid4(),
                    user_id=1,
                    title=f"Event {i}",
                    event_type="race",
                    start_date=date(2026, i + 1, 1),
                )
            )

        page1 = await repo.list_for_user(user_id=1, limit=2, offset=0)
        page2 = await repo.list_for_user(user_id=1, limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    async def test_count_for_user(self, repo: FakeRideEventRepo):
        assert await repo.count_for_user(user_id=1) == 0

        await repo.save(
            RideEvent(id=uuid4(), user_id=1, title="Event 1", event_type="race", start_date=date(2026, 1, 1))
        )
        await repo.save(
            RideEvent(id=uuid4(), user_id=1, title="Event 2", event_type="multi_day", start_date=date(2026, 2, 1))
        )
        await repo.save(
            RideEvent(id=uuid4(), user_id=2, title="Other User", event_type="race", start_date=date(2026, 3, 1))
        )

        assert await repo.count_for_user(user_id=1) == 2
        assert await repo.count_for_user(user_id=2) == 1
        assert await repo.count_for_user(user_id=1, event_type="race") == 1

    async def test_delete_event(self, repo: FakeRideEventRepo):
        event_id = uuid4()
        await repo.save(
            RideEvent(id=event_id, user_id=1, title="To Delete", event_type="race", start_date=date(2026, 1, 1))
        )

        # Wrong user can't delete
        assert await repo.delete(event_id, user_id=2) is False

        # Owner can delete
        assert await repo.delete(event_id, user_id=1) is True
        assert await repo.get_by_id(event_id, user_id=1) is None

        # Can't delete again
        assert await repo.delete(event_id, user_id=1) is False

    async def test_save_requires_user_id(self, repo: FakeRideEventRepo):
        event = RideEvent(
            id=uuid4(),
            user_id=None,  # type: ignore
            title="No User",
            event_type="race",
            start_date=date(2026, 1, 1),
        )

        with pytest.raises(ValueError, match="user_id"):
            await repo.save(event)

    async def test_clear_removes_all(self, repo: FakeRideEventRepo):
        await repo.save(
            RideEvent(id=uuid4(), user_id=1, title="Event 1", event_type="race", start_date=date(2026, 1, 1))
        )
        await repo.save(
            RideEvent(id=uuid4(), user_id=1, title="Event 2", event_type="race", start_date=date(2026, 2, 1))
        )

        repo.clear()
        assert len(repo.all()) == 0


class TestFakeJournalEntryRepo:
    """Tests for FakeJournalEntryRepo."""

    @pytest.fixture
    def event_id(self):
        return uuid4()

    @pytest.fixture
    def repo(self, event_id):
        repo = FakeJournalEntryRepo()
        # Set up event ownership for access control
        repo.set_event_owners({event_id: 1})
        return repo

    async def test_save_and_get_entry(self, repo: FakeJournalEntryRepo, event_id):
        entry_id = uuid4()
        entry = JournalEntry(
            id=entry_id,
            ride_event_id=event_id,
            entry_date=date(2026, 7, 1),
            description="Day 1: Col du Galibier - Amazing climb today!",
        )

        saved = await repo.save(entry)
        assert saved.id == entry_id

        found = await repo.get_by_id(entry_id, user_id=1)
        assert found is not None
        assert found.description == "Day 1: Col du Galibier - Amazing climb today!"

    async def test_get_returns_none_for_wrong_user(self, repo: FakeJournalEntryRepo, event_id):
        entry_id = uuid4()
        entry = JournalEntry(
            id=entry_id,
            ride_event_id=event_id,
            entry_date=date(2026, 7, 1),
            description="Private Entry",
        )
        await repo.save(entry)

        # Different user can't access
        found = await repo.get_by_id(entry_id, user_id=2)
        assert found is None

    async def test_list_for_event_sorted_by_date(self, repo: FakeJournalEntryRepo, event_id):
        entry1 = JournalEntry(id=uuid4(), ride_event_id=event_id, entry_date=date(2026, 7, 3), description="Day 3")
        entry2 = JournalEntry(id=uuid4(), ride_event_id=event_id, entry_date=date(2026, 7, 1), description="Day 1")
        entry3 = JournalEntry(id=uuid4(), ride_event_id=event_id, entry_date=date(2026, 7, 2), description="Day 2")

        await repo.save(entry1)
        await repo.save(entry2)
        await repo.save(entry3)

        entries = await repo.list_for_event(event_id)
        assert len(entries) == 3
        # Should be sorted by entry_date ascending (chronological)
        assert entries[0].description == "Day 1"
        assert entries[1].description == "Day 2"
        assert entries[2].description == "Day 3"

    async def test_delete_entry(self, repo: FakeJournalEntryRepo, event_id):
        entry_id = uuid4()
        entry = JournalEntry(id=entry_id, ride_event_id=event_id, entry_date=date(2026, 7, 1), description="To Delete")
        await repo.save(entry)

        # Wrong user can't delete
        assert await repo.delete(entry_id, user_id=2) is False

        # Owner can delete
        assert await repo.delete(entry_id, user_id=1) is True
        assert await repo.get_by_id(entry_id, user_id=1) is None


class TestFakeRideEventMediaRepo:
    """Tests for FakeRideEventMediaRepo."""

    @pytest.fixture
    def event_id(self):
        return uuid4()

    @pytest.fixture
    def entry_id(self):
        return uuid4()

    @pytest.fixture
    def repo(self, event_id, entry_id):
        repo = FakeRideEventMediaRepo()
        repo.set_event_owners({event_id: 1})
        repo.set_entry_event_map({entry_id: event_id})
        return repo

    async def test_save_and_get_event_media(self, repo: FakeRideEventMediaRepo, event_id):
        media_id = uuid4()
        media = RideEventMedia(
            id=media_id,
            ride_event_id=event_id,
            media_type="photo",
            storage_path="/uploads/photo1.jpg",
            thumbnail_path="/uploads/thumb_photo1.jpg",
            sort_order=0,
        )

        saved = await repo.save(media)
        assert saved.id == media_id

        found = await repo.get_by_id(media_id, user_id=1)
        assert found is not None
        assert found.media_type == "photo"

    async def test_save_and_get_entry_media(self, repo: FakeRideEventMediaRepo, entry_id):
        media_id = uuid4()
        media = RideEventMedia(
            id=media_id,
            journal_entry_id=entry_id,
            media_type="photo",
            storage_path="/uploads/entry_photo.jpg",
            sort_order=0,
        )

        await repo.save(media)

        found = await repo.get_by_id(media_id, user_id=1)
        assert found is not None

    async def test_list_for_event_sorted(self, repo: FakeRideEventMediaRepo, event_id):
        for i in [2, 0, 1]:  # Save out of order
            await repo.save(
                RideEventMedia(
                    id=uuid4(),
                    ride_event_id=event_id,
                    media_type="photo",
                    storage_path=f"/uploads/photo{i}.jpg",
                    sort_order=i,
                )
            )

        media = await repo.list_for_event(event_id)
        assert len(media) == 3
        assert [m.sort_order for m in media] == [0, 1, 2]

    async def test_list_for_entry_sorted(self, repo: FakeRideEventMediaRepo, entry_id):
        for i in [1, 0]:
            await repo.save(
                RideEventMedia(
                    id=uuid4(),
                    journal_entry_id=entry_id,
                    media_type="photo",
                    storage_path=f"/uploads/entry_photo{i}.jpg",
                    sort_order=i,
                )
            )

        media = await repo.list_for_entry(entry_id)
        assert len(media) == 2
        assert media[0].sort_order == 0
        assert media[1].sort_order == 1

    async def test_delete_media(self, repo: FakeRideEventMediaRepo, event_id):
        media_id = uuid4()
        await repo.save(
            RideEventMedia(
                id=media_id,
                ride_event_id=event_id,
                media_type="photo",
                storage_path="/uploads/delete_me.jpg",
                sort_order=0,
            )
        )

        # Wrong user can't delete
        assert await repo.delete(media_id, user_id=2) is False

        # Owner can delete
        assert await repo.delete(media_id, user_id=1) is True
        assert await repo.get_by_id(media_id, user_id=1) is None


class TestFakeRideEventLinkRepo:
    """Tests for FakeRideEventLinkRepo."""

    @pytest.fixture
    def event_id(self):
        return uuid4()

    @pytest.fixture
    def repo(self, event_id):
        repo = FakeRideEventLinkRepo()
        repo.set_event_owners({event_id: 1})
        return repo

    async def test_save_and_get_link(self, repo: FakeRideEventLinkRepo, event_id):
        link_id = uuid4()
        link = RideEventLink(
            id=link_id,
            ride_event_id=event_id,
            url="https://strava.com/routes/12345",
            title="Event Route",
            sort_order=0,
        )

        saved = await repo.save(link)
        assert saved.id == link_id

        found = await repo.get_by_id(link_id, user_id=1)
        assert found is not None
        assert found.title == "Event Route"

    async def test_list_for_event_sorted(self, repo: FakeRideEventLinkRepo, event_id):
        for i in [2, 0, 1]:
            await repo.save(
                RideEventLink(
                    id=uuid4(),
                    ride_event_id=event_id,
                    url=f"https://example.com/{i}",
                    title=f"Link {i}",
                    sort_order=i,
                )
            )

        links = await repo.list_for_event(event_id)
        assert len(links) == 3
        assert [l.sort_order for l in links] == [0, 1, 2]

    async def test_delete_link(self, repo: FakeRideEventLinkRepo, event_id):
        link_id = uuid4()
        await repo.save(
            RideEventLink(
                id=link_id,
                ride_event_id=event_id,
                url="https://delete.me",
                title="Delete Me",
                sort_order=0,
            )
        )

        assert await repo.delete(link_id, user_id=2) is False
        assert await repo.delete(link_id, user_id=1) is True
        assert await repo.get_by_id(link_id, user_id=1) is None


class TestFakeJournalEntryActivityRepo:
    """Tests for FakeJournalEntryActivityRepo."""

    @pytest.fixture
    def entry_id(self):
        return uuid4()

    @pytest.fixture
    def event_id(self):
        return uuid4()

    @pytest.fixture
    def repo(self, entry_id, event_id):
        repo = FakeJournalEntryActivityRepo()
        repo.set_entry_event_map({entry_id: event_id})
        return repo

    async def test_link_and_list_activities(self, repo: FakeJournalEntryActivityRepo, entry_id):
        activity1_id = uuid4()
        activity2_id = uuid4()

        await repo.link(entry_id, activity1_id, sort_order=0)
        await repo.link(entry_id, activity2_id, sort_order=1)

        links = await repo.list_for_entry(entry_id)
        assert len(links) == 2
        assert links[0].activity_id == activity1_id
        assert links[1].activity_id == activity2_id

    async def test_list_for_event(self, repo: FakeJournalEntryActivityRepo, entry_id, event_id):
        activity_id = uuid4()
        await repo.link(entry_id, activity_id, sort_order=0)

        links = await repo.list_for_event(event_id)
        assert len(links) == 1
        assert links[0].activity_id == activity_id

    async def test_unlink_activity(self, repo: FakeJournalEntryActivityRepo, entry_id):
        activity_id = uuid4()
        await repo.link(entry_id, activity_id, sort_order=0)

        assert await repo.unlink(entry_id, activity_id) is True
        assert len(await repo.list_for_entry(entry_id)) == 0

        # Can't unlink again
        assert await repo.unlink(entry_id, activity_id) is False

    async def test_reorder_activities(self, repo: FakeJournalEntryActivityRepo, entry_id):
        activity1_id = uuid4()
        activity2_id = uuid4()
        activity3_id = uuid4()

        await repo.link(entry_id, activity1_id, sort_order=0)
        await repo.link(entry_id, activity2_id, sort_order=1)
        await repo.link(entry_id, activity3_id, sort_order=2)

        # Reorder: move activity3 to first position
        await repo.reorder(entry_id, [activity3_id, activity1_id, activity2_id])

        links = await repo.list_for_entry(entry_id)
        assert links[0].activity_id == activity3_id
        assert links[1].activity_id == activity1_id
        assert links[2].activity_id == activity2_id

    async def test_clear_resets_state(self, repo: FakeJournalEntryActivityRepo, entry_id):
        await repo.link(entry_id, uuid4(), sort_order=0)
        await repo.link(entry_id, uuid4(), sort_order=1)

        repo.clear()
        assert len(repo.all()) == 0
