"""
In-memory fake implementations of repository protocols for unit testing.

These fakes allow testing use cases and business logic without a database,
making tests fast, isolated, and deterministic.

Usage pattern:
    from tests.fakes import FakeUserRepo, FakeActivityRepo

    async def test_some_use_case():
        user_repo = FakeUserRepo()
        activity_repo = FakeActivityRepo()

        # Seed test data
        user = User(id=1, email="test@example.com", ...)
        await user_repo.save(user)

        # Test business logic
        result = await some_use_case(user_repo, activity_repo, ...)

        # Assert on results and repo state
        assert result == expected

Benefits over testcontainers:
- ~100x faster test execution (no container startup)
- Fully deterministic (no external state)
- Easy to inspect internal state for assertions
- No Docker dependency required
"""

from tests.fakes.activity_repo import FakeActivityRepo
from tests.fakes.audit_log_repo import FakeAuditLogRepo
from tests.fakes.credentials_repo import FakeGarminCredentialsRepo, FakeXertCredentialsRepo
from tests.fakes.event_repo import FakeEventRepo
from tests.fakes.notification_repo import FakeNotificationRepo
from tests.fakes.oauth_link_repo import FakeOAuthLinkRepo
from tests.fakes.recalculation_job_repo import FakeRecalculationJobRepo
from tests.fakes.settings_repo import FakeAppSettingsRepo
from tests.fakes.user_repo import FakeUserRepo

__all__ = [
    "FakeActivityRepo",
    "FakeAppSettingsRepo",
    "FakeAuditLogRepo",
    "FakeEventRepo",
    "FakeGarminCredentialsRepo",
    "FakeNotificationRepo",
    "FakeOAuthLinkRepo",
    "FakeRecalculationJobRepo",
    "FakeUserRepo",
    "FakeXertCredentialsRepo",
]
