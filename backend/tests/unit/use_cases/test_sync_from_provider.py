"""Unit tests for SyncFromProvider use case."""

from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest

from trainingdash.crypto import EncryptionError
from trainingdash.integrations.protocols import CredentialInfo
from trainingdash.use_cases import SyncFromProvider


class MockAsyncSession:
    """Minimal mock for AsyncSession."""

    async def execute(self, query):
        return mock.MagicMock(scalar_one_or_none=mock.MagicMock(return_value=None))

    async def commit(self):
        pass


@pytest.fixture
def db_session():
    return MockAsyncSession()


@pytest.fixture
def use_case(db_session):
    return SyncFromProvider(db_session)


class TestDetermineSyncRange:
    """Tests for _determine_sync_range logic."""

    def test_first_sync_with_sync_since(self, use_case):
        """First sync uses sync_since when set."""
        cred_info = CredentialInfo(
            email="test@example.com",
            encrypted_password="encrypted",
            sync_since=datetime(2024, 1, 1),
            last_synced_at=None,
        )

        start, end, is_first = use_case._determine_sync_range(cred_info, set())

        assert is_first is True
        assert start == datetime(2024, 1, 1, 0, 0, 0)
        assert end <= datetime.now(UTC).replace(tzinfo=None)

    def test_first_sync_without_sync_since_uses_90_days(self, use_case):
        """First sync without sync_since defaults to 90 days."""
        cred_info = CredentialInfo(
            email="test@example.com",
            encrypted_password="encrypted",
            sync_since=None,
            last_synced_at=None,
        )

        start, end, is_first = use_case._determine_sync_range(cred_info, set())

        assert is_first is True
        # Start should be approximately 90 days ago
        expected_start = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=90)
        assert abs((start - expected_start).total_seconds()) < 60  # Within 1 minute

    def test_incremental_sync_uses_last_synced_at_minus_4h(self, use_case):
        """Incremental sync uses last_synced_at - 4 hours."""
        last_sync = datetime(2024, 3, 10, 12, 0, 0)
        cred_info = CredentialInfo(
            email="test@example.com",
            encrypted_password="encrypted",
            sync_since=None,
            last_synced_at=last_sync,
        )
        existing_refs = {"xert:123"}  # Has existing activities

        start, end, is_first = use_case._determine_sync_range(cred_info, existing_refs)

        assert is_first is False
        assert start == last_sync - timedelta(hours=4)

    def test_subsequent_sync_without_last_synced_at_uses_90_days(self, use_case):
        """Subsequent sync without last_synced_at falls back to 90 days."""
        cred_info = CredentialInfo(
            email="test@example.com",
            encrypted_password="encrypted",
            sync_since=None,
            last_synced_at=None,
        )
        existing_refs = {"xert:123"}  # Has existing activities

        start, end, is_first = use_case._determine_sync_range(cred_info, existing_refs)

        assert is_first is False
        expected_start = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=90)
        assert abs((start - expected_start).total_seconds()) < 60


class TestSyncFromProviderUseCase:
    @pytest.mark.asyncio
    async def test_execute_no_credentials_returns_error(self, use_case):
        """Missing credentials returns error result."""
        mock_provider = mock.MagicMock()
        mock_provider.source_name = "xert"

        # Mock _get_credentials to return None (no credentials found)
        with mock.patch.object(use_case, "_get_credentials", new_callable=mock.AsyncMock, return_value=None):
            result = await use_case.execute(user_id=1, provider=mock_provider)

        assert result.success is False
        assert "credentials" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_decrypt_failure_returns_error(self, use_case):
        """Failed credential decryption returns error result."""
        mock_provider = mock.MagicMock()
        mock_provider.source_name = "xert"

        mock_creds = mock.MagicMock()
        cred_info = CredentialInfo(
            email="test@example.com",
            encrypted_password="bad_encrypted",
            sync_since=None,
            last_synced_at=None,
        )
        mock_provider.extract_credentials.return_value = cred_info

        # Mock _get_credentials to return credentials (not the cred_info, but raw creds)
        with mock.patch.object(use_case, "_get_credentials", new_callable=mock.AsyncMock, return_value=mock_creds):
            with mock.patch(
                "trainingdash.use_cases.sync_from_provider.decrypt", side_effect=EncryptionError("Decrypt failed")
            ):
                result = await use_case.execute(user_id=1, provider=mock_provider)

        assert result.success is False
        assert "decrypt" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_connection_failure_returns_error(self, use_case):
        """Failed provider connection returns error result."""
        mock_provider = mock.MagicMock()
        mock_provider.source_name = "xert"
        mock_provider.connect = mock.AsyncMock(side_effect=Exception("Connection failed"))

        mock_creds = mock.MagicMock()
        cred_info = CredentialInfo(
            email="test@example.com",
            encrypted_password="encrypted",
            sync_since=None,
            last_synced_at=None,
        )
        mock_provider.extract_credentials.return_value = cred_info

        # Mock _get_credentials to return credentials
        with mock.patch.object(use_case, "_get_credentials", new_callable=mock.AsyncMock, return_value=mock_creds):
            # Mock _get_existing_refs since it needs DB access
            with mock.patch.object(use_case, "_get_existing_refs", new_callable=mock.AsyncMock, return_value=set()):
                with mock.patch("trainingdash.use_cases.sync_from_provider.decrypt", return_value="password"):
                    result = await use_case.execute(user_id=1, provider=mock_provider)

        assert result.success is False
        assert "Connection failed" in result.error
