"""Unit tests for _determine_sync_range in sync.py.

Covers all three range-selection paths:
  1. First sync  — sync_since set        → use sync_since as start
  2. First sync  — sync_since not set    → use 90 days ago
  3. Subsequent  — last_synced_at set    → use last_synced_at - 4h (incremental)
  4. Subsequent  — last_synced_at absent → fall back to 90 days
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from trainingdash.sync import _determine_sync_range, SyncProvider


# ---------------------------------------------------------------------------
# Minimal stub provider — only the methods _determine_sync_range calls
# ---------------------------------------------------------------------------

class _StubProvider:
    """Minimal SyncProvider stub for testing _determine_sync_range."""

    def __init__(self, sync_since=None, last_synced_at=None):
        self._sync_since = sync_since
        self._last_synced_at = last_synced_at

    def get_sync_since(self, creds):
        return self._sync_since

    def get_last_synced_at(self, creds):
        return self._last_synced_at

    # Unused abstract stubs — satisfy the interface without inheriting ABC
    source_name = "test"


# Sentinel creds object — _determine_sync_range only passes it through
_CREDS = object()

# Freeze "now" so tests are deterministic
_NOW = datetime(2026, 8, 6, 12, 0, 0)  # noon UTC, naive


@pytest.fixture(autouse=True)
def freeze_now():
    """Pin datetime.now() to _NOW for all tests in this module."""
    frozen = datetime(2026, 8, 6, 12, 0, 0)
    with mock.patch(
        "trainingdash.sync.datetime",
        wraps=datetime,  # keep strptime etc. working
    ) as m:
        m.now.return_value = frozen
        m.combine = datetime.combine
        m.min = datetime.min
        yield frozen


# ---------------------------------------------------------------------------
# First-sync path
# ---------------------------------------------------------------------------

class TestFirstSync:
    """existing_refs is empty → is_first_sync=True."""

    def test_uses_sync_since_when_set(self, freeze_now):
        sync_since = datetime(2026, 1, 1, 0, 0, 0)
        provider = _StubProvider(sync_since=sync_since)

        start, end, is_first = _determine_sync_range(_CREDS, provider, set())

        assert is_first is True
        assert start == sync_since
        assert end == freeze_now

    def test_uses_sync_since_date_object(self, freeze_now):
        """sync_since may be a date (no .hour) — should be combined with midnight."""
        from datetime import date

        sync_date = date(2026, 3, 15)
        provider = _StubProvider(sync_since=sync_date)

        start, end, is_first = _determine_sync_range(_CREDS, provider, set())

        assert is_first is True
        assert start == datetime(2026, 3, 15, 0, 0, 0)

    def test_defaults_to_90_days_when_no_sync_since(self, freeze_now):
        provider = _StubProvider(sync_since=None)

        start, end, is_first = _determine_sync_range(_CREDS, provider, set())

        assert is_first is True
        expected_start = freeze_now - timedelta(days=90)
        assert start == expected_start

    def test_last_synced_at_ignored_on_first_sync(self, freeze_now):
        """Even if last_synced_at is somehow set, first sync should not use it."""
        provider = _StubProvider(
            sync_since=None,
            last_synced_at=datetime(2026, 8, 5, 12, 0, 0),
        )

        start, end, is_first = _determine_sync_range(_CREDS, provider, set())

        # Still a first sync — existing_refs is empty
        assert is_first is True
        # Should use 90 days, not last_synced_at
        assert start == freeze_now - timedelta(days=90)


# ---------------------------------------------------------------------------
# Subsequent-sync path
# ---------------------------------------------------------------------------

class TestSubsequentSync:
    """existing_refs is non-empty → is_first_sync=False."""

    _EXISTING = {"xert:abc123"}  # one existing ref is enough

    def test_incremental_window_uses_last_synced_at_minus_4h(self, freeze_now):
        last_synced = datetime(2026, 8, 6, 8, 0, 0)  # 4 hours before noon
        provider = _StubProvider(last_synced_at=last_synced)

        start, end, is_first = _determine_sync_range(_CREDS, provider, self._EXISTING)

        assert is_first is False
        assert start == last_synced - timedelta(hours=4)
        assert end == freeze_now

    def test_buffer_covers_4_hours(self, freeze_now):
        """start should be exactly last_synced_at - 4h, not ±1 second."""
        last_synced = datetime(2026, 8, 5, 23, 30, 0)
        provider = _StubProvider(last_synced_at=last_synced)

        start, _, _ = _determine_sync_range(_CREDS, provider, self._EXISTING)

        assert start == datetime(2026, 8, 5, 19, 30, 0)

    def test_falls_back_to_90_days_when_no_last_synced_at(self, freeze_now):
        """Existing refs but no last_synced_at → 90-day window (legacy behaviour)."""
        provider = _StubProvider(last_synced_at=None)

        start, end, is_first = _determine_sync_range(_CREDS, provider, self._EXISTING)

        assert is_first is False
        assert start == freeze_now - timedelta(days=90)

    def test_sync_since_ignored_on_subsequent_sync(self, freeze_now):
        """sync_since is only consulted on the first sync."""
        provider = _StubProvider(
            sync_since=datetime(2025, 1, 1),
            last_synced_at=datetime(2026, 8, 6, 10, 0, 0),
        )

        start, _, is_first = _determine_sync_range(_CREDS, provider, self._EXISTING)

        assert is_first is False
        # Should use last_synced_at - 4h, not sync_since
        assert start == datetime(2026, 8, 6, 6, 0, 0)
