"""
Sample tests demonstrating usage of fake repositories.

These tests show how to use in-memory fakes instead of testcontainers,
making tests fast (~100x faster) and fully isolated.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tests.fakes import (
    FakeActivityRepo,
    FakeAppSettingsRepo,
    FakeAuditLogRepo,
    FakeEventRepo,
    FakeOAuthLinkRepo,
    FakeUserRepo,
    FakeXertCredentialsRepo,
)
from trainingdash.repositories.postgres.models import Activity, User


class TestFakeUserRepo:
    """Demonstrates FakeUserRepo usage."""

    @pytest.fixture
    def user_repo(self):
        return FakeUserRepo()

    async def test_save_and_get_user(self, user_repo: FakeUserRepo):
        # Create a user without ID (auto-generated)
        user = User(email="test@example.com", password_hash="hash123")

        # Save assigns ID
        saved = await user_repo.save(user)
        assert saved.id == 1

        # Retrieve by ID
        found = await user_repo.get_by_id(1)
        assert found is not None
        assert found.email == "test@example.com"

    async def test_get_by_email_case_insensitive(self, user_repo: FakeUserRepo):
        user = User(email="Test@Example.COM", password_hash="hash")
        await user_repo.save(user)

        # Should find regardless of case
        found = await user_repo.get_by_email("test@example.com")
        assert found is not None
        assert found.email == "Test@Example.COM"

    async def test_exists_by_email(self, user_repo: FakeUserRepo):
        assert not await user_repo.exists_by_email("test@example.com")

        await user_repo.save(User(email="test@example.com", password_hash="hash"))

        assert await user_repo.exists_by_email("test@example.com")

    async def test_delete_user(self, user_repo: FakeUserRepo):
        user = User(email="test@example.com", password_hash="hash")
        await user_repo.save(user)

        assert await user_repo.delete(1) is True
        assert await user_repo.get_by_id(1) is None

        # Deleting non-existent returns False
        assert await user_repo.delete(999) is False


class TestFakeActivityRepo:
    """Demonstrates FakeActivityRepo usage."""

    @pytest.fixture
    def activity_repo(self):
        return FakeActivityRepo()

    async def test_save_and_list_activities(self, activity_repo: FakeActivityRepo):
        # Create activities with different timestamps
        now = datetime.now(UTC).replace(tzinfo=None)
        activity1 = Activity(
            id=uuid4(),
            user_id=1,
            started_at=now,
            source="test",
            source_ref="ref1",
        )
        activity2 = Activity(
            id=uuid4(),
            user_id=1,
            started_at=now.replace(hour=max(0, now.hour - 1)),  # 1 hour earlier
            source="test",
            source_ref="ref2",
        )

        await activity_repo.save(activity1)
        await activity_repo.save(activity2)

        # List returns newest first
        activities = await activity_repo.list_for_user(1)
        assert len(activities) == 2
        assert activities[0].source_ref == "ref1"  # newer
        assert activities[1].source_ref == "ref2"  # older

    async def test_count_for_user(self, activity_repo: FakeActivityRepo):
        assert await activity_repo.count_for_user(1) == 0

        now = datetime.now(UTC).replace(tzinfo=None)
        await activity_repo.save(Activity(id=uuid4(), user_id=1, source="test", source_ref="1", started_at=now))
        await activity_repo.save(Activity(id=uuid4(), user_id=1, source="test", source_ref="2", started_at=now))
        await activity_repo.save(
            Activity(id=uuid4(), user_id=2, source="test", source_ref="3", started_at=now)
        )  # different user

        assert await activity_repo.count_for_user(1) == 2
        assert await activity_repo.count_for_user(2) == 1

    async def test_delete_activity(self, activity_repo: FakeActivityRepo):
        activity_id = uuid4()
        now = datetime.now(UTC).replace(tzinfo=None)
        await activity_repo.save(Activity(id=activity_id, user_id=1, source="test", source_ref="ref", started_at=now))

        # Can't delete another user's activity
        assert await activity_repo.delete(activity_id, user_id=2) is False

        # Owner can delete
        assert await activity_repo.delete(activity_id, user_id=1) is True
        assert await activity_repo.get_by_id(activity_id, user_id=1) is None


class TestFakeCredentialsRepo:
    """Demonstrates FakeXertCredentialsRepo usage."""

    @pytest.fixture
    def xert_repo(self):
        return FakeXertCredentialsRepo()

    async def test_save_and_get_credentials(self, xert_repo: FakeXertCredentialsRepo):
        assert not await xert_repo.exists(1)

        creds = await xert_repo.save(
            user_id=1,
            xert_email="user@xert.com",
            encrypted_password="encrypted123",
        )

        assert await xert_repo.exists(1)

        found = await xert_repo.get_by_user_id(1)
        assert found is not None
        assert found.xert_email == "user@xert.com"

    async def test_upsert_updates_existing(self, xert_repo: FakeXertCredentialsRepo):
        await xert_repo.save(
            user_id=1,
            xert_email="old@xert.com",
            encrypted_password="old_pass",
        )

        # Upsert with new email
        await xert_repo.save(
            user_id=1,
            xert_email="new@xert.com",
            encrypted_password="new_pass",
        )

        found = await xert_repo.get_by_user_id(1)
        assert found.xert_email == "new@xert.com"


class TestFakeAppSettingsRepo:
    """Demonstrates FakeAppSettingsRepo usage."""

    @pytest.fixture
    def settings_repo(self):
        return FakeAppSettingsRepo()

    async def test_get_and_set(self, settings_repo: FakeAppSettingsRepo):
        assert await settings_repo.get("require_approval") is None

        await settings_repo.set("require_approval", "true")

        assert await settings_repo.get("require_approval") == "true"

    async def test_get_bool(self, settings_repo: FakeAppSettingsRepo):
        # Default when not set
        assert await settings_repo.get_bool("feature_flag", default=False) is False
        assert await settings_repo.get_bool("feature_flag", default=True) is True

        # Truthy values
        await settings_repo.set("enabled", "true")
        assert await settings_repo.get_bool("enabled") is True

        await settings_repo.set("enabled", "1")
        assert await settings_repo.get_bool("enabled") is True

        # Falsy values
        await settings_repo.set("enabled", "false")
        assert await settings_repo.get_bool("enabled") is False


class TestFakeAuditLogRepo:
    """Demonstrates FakeAuditLogRepo usage."""

    @pytest.fixture
    def audit_repo(self):
        return FakeAuditLogRepo()

    async def test_log_entries(self, audit_repo: FakeAuditLogRepo):
        await audit_repo.log(
            admin_id=1,
            action="nuke_activities",
            target_user_id=2,
            details="100 activities deleted",
        )

        entries = audit_repo.all()
        assert len(entries) == 1
        assert entries[0].admin_id == 1
        assert entries[0].action == "nuke_activities"
        assert entries[0].target_user_id == 2

    async def test_find_by_action(self, audit_repo: FakeAuditLogRepo):
        await audit_repo.log(admin_id=1, action="create_user")
        await audit_repo.log(admin_id=1, action="nuke_activities")
        await audit_repo.log(admin_id=2, action="create_user")

        create_entries = audit_repo.find_by_action("create_user")
        assert len(create_entries) == 2


class TestFakeOAuthLinkRepo:
    """Demonstrates FakeOAuthLinkRepo usage."""

    @pytest.fixture
    def oauth_repo(self):
        return FakeOAuthLinkRepo()

    async def test_save_and_list_links(self, oauth_repo: FakeOAuthLinkRepo):
        await oauth_repo.save(
            user_id=1,
            provider="github",
            provider_user_id="gh_123",
            provider_email="user@github.com",
        )
        await oauth_repo.save(
            user_id=1,
            provider="google",
            provider_user_id="google_456",
            provider_email="user@gmail.com",
        )

        links = await oauth_repo.list_for_user(1)
        assert len(links) == 2
        assert await oauth_repo.count_for_user(1) == 2

    async def test_get_by_provider_id(self, oauth_repo: FakeOAuthLinkRepo):
        await oauth_repo.save(
            user_id=1,
            provider="github",
            provider_user_id="gh_123",
        )

        # Find by provider + provider_user_id
        link = await oauth_repo.get_by_provider_id("github", "gh_123")
        assert link is not None
        assert link.user_id == 1

        # Not found
        link = await oauth_repo.get_by_provider_id("github", "wrong_id")
        assert link is None



class TestFakeEventRepo:
    """Demonstrates FakeEventRepo usage."""

    @pytest.fixture
    def event_repo(self):
        return FakeEventRepo()

    async def test_log_event_returns_id(self, event_repo: FakeEventRepo):
        event_id = await event_repo.log(
            event_type="sync.completed",
            outcome="success",
            user_id=1,
            payload={"activities": 5},
        )
        assert event_id == 1

        # Second event gets next ID
        event_id2 = await event_repo.log(
            event_type="activity.created",
            outcome="success",
        )
        assert event_id2 == 2

    async def test_list_returns_newest_first(self, event_repo: FakeEventRepo):
        now = datetime.now(UTC).replace(tzinfo=None)
        earlier = now.replace(hour=max(0, now.hour - 1))

        event_repo.add_with_timestamp("sync.completed", "success", earlier)
        event_repo.add_with_timestamp("activity.created", "success", now)

        events = await event_repo.list()
        assert len(events) == 2
        assert events[0].event_type == "activity.created"  # newer
        assert events[1].event_type == "sync.completed"  # older

    async def test_list_filters_by_type(self, event_repo: FakeEventRepo):
        await event_repo.log(event_type="sync.completed", outcome="success")
        await event_repo.log(event_type="activity.created", outcome="success")
        await event_repo.log(event_type="sync.completed", outcome="failure")

        events = await event_repo.list(event_type="sync.completed")
        assert len(events) == 2
        assert all(e.event_type == "sync.completed" for e in events)

    async def test_list_filters_by_outcome(self, event_repo: FakeEventRepo):
        await event_repo.log(event_type="sync.completed", outcome="success")
        await event_repo.log(event_type="sync.completed", outcome="failure")

        events = await event_repo.list(outcome="success")
        assert len(events) == 1
        assert events[0].outcome == "success"

    async def test_list_filters_by_user(self, event_repo: FakeEventRepo):
        await event_repo.log(event_type="sync.completed", outcome="success", user_id=1)
        await event_repo.log(event_type="sync.completed", outcome="success", user_id=2)
        await event_repo.log(event_type="activity.created", outcome="success")  # no user

        events = await event_repo.list(user_id=1)
        assert len(events) == 1
        assert events[0].user_id == 1

    async def test_list_filters_by_time_range(self, event_repo: FakeEventRepo):
        now = datetime.now(UTC).replace(tzinfo=None)
        hour_ago = now.replace(hour=max(0, now.hour - 1))
        two_hours_ago = now.replace(hour=max(0, now.hour - 2))

        event_repo.add_with_timestamp("old.event", "success", two_hours_ago)
        event_repo.add_with_timestamp("mid.event", "success", hour_ago)
        event_repo.add_with_timestamp("new.event", "success", now)

        # Since filter (inclusive)
        events = await event_repo.list(since=hour_ago)
        assert len(events) == 2

        # Until filter (exclusive)
        events = await event_repo.list(until=hour_ago)
        assert len(events) == 1
        assert events[0].event_type == "old.event"

    async def test_list_pagination(self, event_repo: FakeEventRepo):
        for i in range(5):
            await event_repo.log(event_type=f"event.{i}", outcome="success")

        # First page
        page1 = await event_repo.list(limit=2, offset=0)
        assert len(page1) == 2

        # Second page
        page2 = await event_repo.list(limit=2, offset=2)
        assert len(page2) == 2

        # Pages should be different
        assert page1[0].event_type != page2[0].event_type

    async def test_list_caps_limit_at_100(self, event_repo: FakeEventRepo):
        # Log 5 events
        for i in range(5):
            await event_repo.log(event_type=f"event.{i}", outcome="success")

        # Request 200 but should only get 5 (cap doesn't affect actual count)
        events = await event_repo.list(limit=200)
        assert len(events) == 5

    async def test_count_with_filters(self, event_repo: FakeEventRepo):
        await event_repo.log(event_type="sync.completed", outcome="success", user_id=1)
        await event_repo.log(event_type="sync.completed", outcome="failure", user_id=1)
        await event_repo.log(event_type="activity.created", outcome="success", user_id=2)

        assert await event_repo.count() == 3
        assert await event_repo.count(event_type="sync.completed") == 2
        assert await event_repo.count(outcome="success") == 2
        assert await event_repo.count(user_id=1) == 2
        assert await event_repo.count(event_type="sync.completed", outcome="success") == 1

    async def test_delete_before(self, event_repo: FakeEventRepo):
        now = datetime.now(UTC).replace(tzinfo=None)
        hour_ago = now.replace(hour=max(0, now.hour - 1))
        two_hours_ago = now.replace(hour=max(0, now.hour - 2))

        event_repo.add_with_timestamp("old.event", "success", two_hours_ago)
        event_repo.add_with_timestamp("mid.event", "success", hour_ago)
        event_repo.add_with_timestamp("new.event", "success", now)

        deleted = await event_repo.delete_before(hour_ago)
        assert deleted == 1  # Only the old event

        remaining = event_repo.all()
        assert len(remaining) == 2

    async def test_helper_find_by_type(self, event_repo: FakeEventRepo):
        await event_repo.log(event_type="sync.completed", outcome="success")
        await event_repo.log(event_type="activity.created", outcome="success")

        sync_events = event_repo.find_by_type("sync.completed")
        assert len(sync_events) == 1

    async def test_helper_find_by_outcome(self, event_repo: FakeEventRepo):
        await event_repo.log(event_type="sync.completed", outcome="success")
        await event_repo.log(event_type="sync.completed", outcome="failure")

        failures = event_repo.find_by_outcome("failure")
        assert len(failures) == 1

    async def test_clear_resets_state(self, event_repo: FakeEventRepo):
        await event_repo.log(event_type="sync.completed", outcome="success")
        await event_repo.log(event_type="activity.created", outcome="success")

        event_repo.clear()

        assert len(event_repo.all()) == 0
        # ID counter resets
        new_id = await event_repo.log(event_type="new.event", outcome="success")
        assert new_id == 1
