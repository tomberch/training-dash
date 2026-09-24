"""Unit tests for ImportFromProvider use case — segment job chaining."""

import uuid
from datetime import datetime
from unittest import mock

import pytest

from trainingdash.integrations.protocols import CredentialInfo
from trainingdash.use_cases import ImportFromProvider


class MockAsyncSession:
    """Minimal mock for AsyncSession."""

    def add(self, obj):
        pass

    async def flush(self):
        pass

    async def execute(self, query):
        # Return None for credential lookups and empty for ref lookups
        m = mock.MagicMock()
        m.scalar_one_or_none = mock.MagicMock(return_value=None)
        m.scalar_one = mock.MagicMock(return_value=None)
        m.scalars = mock.MagicMock(return_value=mock.MagicMock(all=mock.MagicMock(return_value=[])))
        return m

    async def commit(self):
        pass


class FakeActivity:
    """Minimal stand-in for an ingested Activity."""

    def __init__(self):
        self.id = uuid.uuid4()


class FakeProviderActivity:
    """Minimal stand-in for ProviderActivity."""

    def __init__(self, provider_id):
        self.id = provider_id
        self.started_at = datetime(2026, 9, 20, 12, 0, 0)
        self.distance_m = 10000.0
        self.raw = None


class FakeCredsModel:
    """Stand-in for an ORM credentials model."""

    user_id = None


class ChainingStubProvider:
    """Provider stub that succeeds for all listed activities.

    Implements the ImportProvider protocol surface used by ImportFromProvider.
    """

    def __init__(self, provider_activity_ids):
        self._ids = provider_activity_ids
        self.ingested_ids = []

    @property
    def source_name(self):
        return "xert"

    @property
    def credentials_model(self):
        return FakeCredsModel

    def extract_credentials(self, creds):
        return CredentialInfo(
            email="e@example.com",
            encrypted_password="enc",
            sync_since=None,
            last_synced_at=None,
        )

    async def connect(self, email, password):
        pass

    async def list_activities(self, start_date, end_date):
        return [FakeProviderActivity(i) for i in self._ids]

    def make_source_ref(self, provider_id):
        return f"xert:{provider_id}"

    async def ingest_activity(self, db, user_id, activity, batch_mode):
        self.ingested_ids.append(activity.id)
        return FakeActivity()

    async def close(self):
        pass


def make_use_case():
    db = MockAsyncSession()
    use_case = ImportFromProvider(db)
    # Stub credential + ref lookups — these unit tests target chaining behavior,
    # not SQLAlchemy plumbing.
    use_case._get_credentials = mock.AsyncMock(return_value=mock.MagicMock())
    use_case._get_existing_refs = mock.AsyncMock(return_value=set())
    return use_case


@pytest.fixture
def patched_crypto():
    with mock.patch("trainingdash.use_cases.import_from_provider.decrypt", return_value="pw"):
        yield


class TestImportChainsSegmentProcessing:
    """ImportFromProvider must enqueue segment processing for each imported activity."""

    @pytest.mark.asyncio
    async def test_enqueues_segment_process_job_for_each_imported_activity(self, patched_crypto):
        use_case = make_use_case()
        provider = ChainingStubProvider(["a1", "a2", "a3"])

        with mock.patch(
            "trainingdash.jobs.enqueue_segment_process_job",
            new_callable=mock.AsyncMock,
        ) as enqueue:
            result = await use_case.execute(user_id=3, provider=provider)

        assert result.success is True
        assert result.imported_activities == 3
        assert enqueue.await_count == 3
        # Each call carries the user id (positional or keyword)
        for call in enqueue.await_args_list:
            args, kwargs = call
            assert kwargs.get("user_id", args[1] if len(args) > 1 else None) == 3

    @pytest.mark.asyncio
    async def test_does_not_enqueue_for_failed_ingest(self, patched_crypto):
        use_case = make_use_case()

        class FailFirstProvider(ChainingStubProvider):
            async def ingest_activity(self, db, user_id, activity, batch_mode):
                if activity.id == "bad":
                    return None
                return FakeActivity()

        provider = FailFirstProvider(["bad", "good"])

        with mock.patch(
            "trainingdash.jobs.enqueue_segment_process_job",
            new_callable=mock.AsyncMock,
        ) as enqueue:
            result = await use_case.execute(user_id=3, provider=provider)

        assert result.imported_activities == 1
        assert enqueue.await_count == 1

    @pytest.mark.asyncio
    async def test_enqueue_failure_does_not_break_import(self, patched_crypto):
        """A queue hiccup must not fail the import — the activity is already saved."""
        use_case = make_use_case()
        provider = ChainingStubProvider(["a1"])

        with mock.patch(
            "trainingdash.jobs.enqueue_segment_process_job",
            new_callable=mock.AsyncMock,
            side_effect=Exception("queue down"),
        ):
            result = await use_case.execute(user_id=3, provider=provider)

        assert result.success is True
        assert result.imported_activities == 1
