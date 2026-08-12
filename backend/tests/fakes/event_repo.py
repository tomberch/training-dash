"""In-memory fake implementation of EventRepo for testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class FakeEvent:
    """Simple data class representing an event for testing."""

    id: int
    created_at: datetime
    event_type: str
    outcome: str
    user_id: int | None
    payload: dict = field(default_factory=dict)


class FakeEventRepo:
    """
    In-memory fake implementation of EventRepo protocol.

    Stores events in a list with auto-incrementing IDs.
    """

    def __init__(self) -> None:
        self._events: list[FakeEvent] = []
        self._next_id: int = 1

    # --- Protocol methods ---

    async def log(
        self,
        event_type: str,
        outcome: str,
        user_id: int | None = None,
        payload: dict | None = None,
    ) -> int:
        """Log an event and return its ID."""
        event = FakeEvent(
            id=self._next_id,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            event_type=event_type,
            outcome=outcome,
            user_id=user_id,
            payload=payload or {},
        )
        self._next_id += 1
        self._events.append(event)
        return event.id

    async def list(
        self,
        event_type: str | None = None,
        outcome: str | None = None,
        user_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FakeEvent]:
        """List events with optional filters, ordered by created_at descending."""
        # Cap limit at 100
        limit = min(limit, 100)

        # Filter events
        result = self._events

        if event_type is not None:
            result = [e for e in result if e.event_type == event_type]
        if outcome is not None:
            result = [e for e in result if e.outcome == outcome]
        if user_id is not None:
            result = [e for e in result if e.user_id == user_id]
        if since is not None:
            result = [e for e in result if e.created_at >= since]
        if until is not None:
            result = [e for e in result if e.created_at < until]

        # Sort by created_at descending
        result = sorted(result, key=lambda e: e.created_at, reverse=True)

        # Apply pagination
        return result[offset : offset + limit]

    async def count(
        self,
        event_type: str | None = None,
        outcome: str | None = None,
        user_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        """Count events matching the given filters."""
        # Reuse list logic without pagination
        filtered = await self.list(
            event_type=event_type,
            outcome=outcome,
            user_id=user_id,
            since=since,
            until=until,
            limit=100000,  # Effectively no limit
            offset=0,
        )
        return len(filtered)

    async def delete_before(self, cutoff: datetime, batch_size: int = 1000) -> int:
        """Delete events older than the cutoff time."""
        original_count = len(self._events)
        self._events = [e for e in self._events if e.created_at >= cutoff]
        return original_count - len(self._events)

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored events and reset ID counter."""
        self._events.clear()
        self._next_id = 1

    def all(self) -> list[FakeEvent]:
        """Return all stored events (for test assertions)."""
        return list(self._events)

    def find_by_type(self, event_type: str) -> list[FakeEvent]:
        """Find events by type."""
        return [e for e in self._events if e.event_type == event_type]

    def find_by_outcome(self, outcome: str) -> list[FakeEvent]:
        """Find events by outcome."""
        return [e for e in self._events if e.outcome == outcome]

    def find_by_user(self, user_id: int) -> list[FakeEvent]:
        """Find events by user ID."""
        return [e for e in self._events if e.user_id == user_id]

    def add_with_timestamp(
        self,
        event_type: str,
        outcome: str,
        created_at: datetime,
        user_id: int | None = None,
        payload: dict | None = None,
    ) -> int:
        """Add an event with a specific timestamp (for testing time-based queries)."""
        event = FakeEvent(
            id=self._next_id,
            created_at=created_at,
            event_type=event_type,
            outcome=outcome,
            user_id=user_id,
            payload=payload or {},
        )
        self._next_id += 1
        self._events.append(event)
        return event.id
