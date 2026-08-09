"""Unit tests for _determine_sync_range in use_cases/sync_from_provider.py.

Covers all four range-selection paths:
  1. First sync  — sync_since set        → use sync_since as start
  2. First sync  — sync_since not set    → use 90 days ago
  3. Subsequent  — last_synced_at set    → use last_synced_at - 4h (incremental)
  4. Subsequent  — last_synced_at absent → fall back to 90 days
"""

from datetime import datetime, timedelta
from unittest import mock

from trainingdash.integrations.protocols import CredentialInfo
from trainingdash.use_cases.sync_from_provider import SyncFromProvider

_determine_sync_range = SyncFromProvider._determine_sync_range


def _cred(sync_since=None, last_synced_at=None) -> CredentialInfo:
    """Build a minimal CredentialInfo for range tests."""
    return CredentialInfo(
        email="test@example.com",
        encrypted_password=b"enc",
        sync_since=sync_since,
        last_synced_at=last_synced_at,
    )


_FROZEN = datetime(2026, 8, 6, 12, 0, 0)


import pytest

@pytest.fixture(autouse=True)
def freeze_now():
    """Pin datetime.now() to _FROZEN for all tests in this module."""
    with mock.patch(
        "trainingdash.use_cases.sync_from_provider.datetime",
        wraps=datetime,
    ) as m:
        m.now.return_value = _FROZEN
        m.combine = datetime.combine
        m.min = datetime.min
        yield _FROZEN


# ---------------------------------------------------------------------------
# First-sync path  (existing_refs is empty)
# ---------------------------------------------------------------------------

class TestFirstSync:
    def test_uses_sync_since_when_set(self, freeze_now):
        sync_since = datetime(2026, 1, 1, 0, 0, 0)
        start, end, is_first = _determine_sync_range(_cred(sync_since=sync_since), set())
        assert is_first is True
        assert start == sync_since
        assert end == freeze_now

    def test_uses_sync_since_date_object(self, freeze_now):
        """sync_since may be a date (no .hour) — should be combined with midnight."""
        from datetime import date
        sync_date = date(2026, 3, 15)
        start, _, is_first = _determine_sync_range(_cred(sync_since=sync_date), set())
        assert is_first is True
        assert start == datetime(2026, 3, 15, 0, 0, 0)

    def test_defaults_to_90_days_when_no_sync_since(self, freeze_now):
        start, _, is_first = _determine_sync_range(_cred(), set())
        assert is_first is True
        assert start == freeze_now - timedelta(days=90)

    def test_last_synced_at_ignored_on_first_sync(self, freeze_now):
        """last_synced_at is irrelevant when existing_refs is empty."""
        cred = _cred(sync_since=None, last_synced_at=datetime(2026, 8, 5, 12, 0, 0))
        start, _, is_first = _determine_sync_range(cred, set())
        assert is_first is True
        assert start == freeze_now - timedelta(days=90)


# ---------------------------------------------------------------------------
# Subsequent-sync path  (existing_refs is non-empty)
# ---------------------------------------------------------------------------

class TestSubsequentSync:
    _EXISTING = {"xert:abc123"}

    def test_incremental_window_uses_last_synced_at_minus_4h(self, freeze_now):
        last_synced = datetime(2026, 8, 6, 8, 0, 0)
        start, end, is_first = _determine_sync_range(
            _cred(last_synced_at=last_synced), self._EXISTING
        )
        assert is_first is False
        assert start == last_synced - timedelta(hours=4)
        assert end == freeze_now

    def test_buffer_covers_exactly_4_hours(self, freeze_now):
        last_synced = datetime(2026, 8, 5, 23, 30, 0)
        start, _, _ = _determine_sync_range(
            _cred(last_synced_at=last_synced), self._EXISTING
        )
        assert start == datetime(2026, 8, 5, 19, 30, 0)

    def test_falls_back_to_90_days_when_no_last_synced_at(self, freeze_now):
        start, _, is_first = _determine_sync_range(_cred(), self._EXISTING)
        assert is_first is False
        assert start == freeze_now - timedelta(days=90)

    def test_sync_since_ignored_on_subsequent_sync(self, freeze_now):
        """sync_since is only consulted on the first sync."""
        cred = _cred(
            sync_since=datetime(2025, 1, 1),
            last_synced_at=datetime(2026, 8, 6, 10, 0, 0),
        )
        start, _, is_first = _determine_sync_range(cred, self._EXISTING)
        assert is_first is False
        assert start == datetime(2026, 8, 6, 6, 0, 0)
