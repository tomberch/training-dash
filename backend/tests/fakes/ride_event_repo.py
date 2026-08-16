"""In-memory fake implementations of RideEvent repositories for testing."""

from datetime import date
from uuid import UUID

from trainingdash.repositories.postgres.models import (
    JournalEntry,
    JournalEntryActivity,
    RideEvent,
    RideEventLink,
    RideEventMedia,
)


class FakeRideEventRepo:
    """
    In-memory fake implementation of RideEventRepo protocol.

    Stores events in a dict keyed by (user_id, event_id).
    """

    def __init__(self) -> None:
        self._events: dict[tuple[int, UUID], RideEvent] = {}

    async def get_by_id(self, event_id: UUID, user_id: int) -> RideEvent | None:
        return self._events.get((user_id, event_id))

    async def list_for_user(
        self,
        user_id: int,
        event_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RideEvent]:
        events = [e for (uid, _), e in self._events.items() if uid == user_id]
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        events.sort(key=lambda e: e.start_date, reverse=True)
        return events[offset : offset + limit]

    async def count_for_user(self, user_id: int, event_type: str | None = None) -> int:
        events = [e for (uid, _), e in self._events.items() if uid == user_id]
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        return len(events)

    async def save(self, event: RideEvent) -> RideEvent:
        if event.user_id is None:
            raise ValueError("RideEvent must have a user_id")
        self._events[(event.user_id, event.id)] = event
        return event

    async def delete(self, event_id: UUID, user_id: int) -> bool:
        key = (user_id, event_id)
        if key in self._events:
            del self._events[key]
            return True
        return False

    # --- Test helpers ---

    def clear(self) -> None:
        """Clear all stored events."""
        self._events.clear()

    def all(self) -> list[RideEvent]:
        """Return all stored events (for test assertions)."""
        return list(self._events.values())


class FakeJournalEntryRepo:
    """
    In-memory fake implementation of JournalEntryRepo protocol.

    Stores entries in a dict keyed by entry_id.
    Requires an optional event_owners dict mapping event_id -> user_id for ownership checks.
    """

    def __init__(self, event_owners: dict[UUID, int] | None = None) -> None:
        self._entries: dict[UUID, JournalEntry] = {}
        self._event_owners = event_owners or {}

    def set_event_owners(self, event_owners: dict[UUID, int]) -> None:
        """Set the mapping of event_id -> user_id for ownership checks."""
        self._event_owners = event_owners

    async def get_by_id(self, entry_id: UUID, user_id: int) -> JournalEntry | None:
        entry = self._entries.get(entry_id)
        if entry is None:
            return None
        # Check event ownership
        owner = self._event_owners.get(entry.ride_event_id)
        if owner != user_id:
            return None
        return entry

    async def list_for_event(self, event_id: UUID) -> list[JournalEntry]:
        entries = [e for e in self._entries.values() if e.ride_event_id == event_id]
        entries.sort(key=lambda e: e.entry_date)
        return entries

    async def save(self, entry: JournalEntry) -> JournalEntry:
        self._entries[entry.id] = entry
        return entry

    async def delete(self, entry_id: UUID, user_id: int) -> bool:
        entry = await self.get_by_id(entry_id, user_id)
        if entry is None:
            return False
        del self._entries[entry_id]
        return True

    # --- Test helpers ---

    def clear(self) -> None:
        self._entries.clear()

    def all(self) -> list[JournalEntry]:
        return list(self._entries.values())


class FakeRideEventMediaRepo:
    """
    In-memory fake implementation of RideEventMediaRepo protocol.
    """

    def __init__(
        self,
        event_owners: dict[UUID, int] | None = None,
        entry_event_map: dict[UUID, UUID] | None = None,
    ) -> None:
        self._media: dict[UUID, RideEventMedia] = {}
        self._event_owners = event_owners or {}
        self._entry_event_map = entry_event_map or {}  # entry_id -> event_id

    def set_event_owners(self, event_owners: dict[UUID, int]) -> None:
        self._event_owners = event_owners

    def set_entry_event_map(self, entry_event_map: dict[UUID, UUID]) -> None:
        self._entry_event_map = entry_event_map

    async def get_by_id(self, media_id: UUID, user_id: int) -> RideEventMedia | None:
        media = self._media.get(media_id)
        if media is None:
            return None
        # Check ownership
        if media.ride_event_id is not None:
            owner = self._event_owners.get(media.ride_event_id)
        elif media.journal_entry_id is not None:
            event_id = self._entry_event_map.get(media.journal_entry_id)
            owner = self._event_owners.get(event_id) if event_id else None
        else:
            return None
        if owner != user_id:
            return None
        return media

    async def list_for_event(self, event_id: UUID) -> list[RideEventMedia]:
        media = [m for m in self._media.values() if m.ride_event_id == event_id]
        media.sort(key=lambda m: m.sort_order)
        return media

    async def list_for_entry(self, entry_id: UUID) -> list[RideEventMedia]:
        media = [m for m in self._media.values() if m.journal_entry_id == entry_id]
        media.sort(key=lambda m: m.sort_order)
        return media

    async def save(self, media: RideEventMedia) -> RideEventMedia:
        self._media[media.id] = media
        return media

    async def delete(self, media_id: UUID, user_id: int) -> bool:
        media = await self.get_by_id(media_id, user_id)
        if media is None:
            return False
        del self._media[media_id]
        return True

    # --- Test helpers ---

    def clear(self) -> None:
        self._media.clear()

    def all(self) -> list[RideEventMedia]:
        return list(self._media.values())


class FakeRideEventLinkRepo:
    """
    In-memory fake implementation of RideEventLinkRepo protocol.
    """

    def __init__(
        self,
        event_owners: dict[UUID, int] | None = None,
        entry_event_map: dict[UUID, UUID] | None = None,
    ) -> None:
        self._links: dict[UUID, RideEventLink] = {}
        self._event_owners = event_owners or {}
        self._entry_event_map = entry_event_map or {}

    def set_event_owners(self, event_owners: dict[UUID, int]) -> None:
        self._event_owners = event_owners

    def set_entry_event_map(self, entry_event_map: dict[UUID, UUID]) -> None:
        self._entry_event_map = entry_event_map

    async def get_by_id(self, link_id: UUID, user_id: int) -> RideEventLink | None:
        link = self._links.get(link_id)
        if link is None:
            return None
        # Check ownership
        if link.ride_event_id is not None:
            owner = self._event_owners.get(link.ride_event_id)
        elif link.journal_entry_id is not None:
            event_id = self._entry_event_map.get(link.journal_entry_id)
            owner = self._event_owners.get(event_id) if event_id else None
        else:
            return None
        if owner != user_id:
            return None
        return link

    async def list_for_event(self, event_id: UUID) -> list[RideEventLink]:
        links = [l for l in self._links.values() if l.ride_event_id == event_id]
        links.sort(key=lambda l: l.sort_order)
        return links

    async def list_for_entry(self, entry_id: UUID) -> list[RideEventLink]:
        links = [l for l in self._links.values() if l.journal_entry_id == entry_id]
        links.sort(key=lambda l: l.sort_order)
        return links

    async def save(self, link: RideEventLink) -> RideEventLink:
        self._links[link.id] = link
        return link

    async def delete(self, link_id: UUID, user_id: int) -> bool:
        link = await self.get_by_id(link_id, user_id)
        if link is None:
            return False
        del self._links[link_id]
        return True

    # --- Test helpers ---

    def clear(self) -> None:
        self._links.clear()

    def all(self) -> list[RideEventLink]:
        return list(self._links.values())


class FakeJournalEntryActivityRepo:
    """
    In-memory fake implementation of JournalEntryActivityRepo protocol.
    """

    def __init__(self, entry_event_map: dict[UUID, UUID] | None = None) -> None:
        self._links: list[JournalEntryActivity] = []
        self._next_id = 1
        self._entry_event_map = entry_event_map or {}

    def set_entry_event_map(self, entry_event_map: dict[UUID, UUID]) -> None:
        self._entry_event_map = entry_event_map

    async def list_for_entry(self, entry_id: UUID) -> list[JournalEntryActivity]:
        links = [l for l in self._links if l.journal_entry_id == entry_id]
        links.sort(key=lambda l: l.sort_order)
        return links

    async def list_for_event(self, event_id: UUID) -> list[JournalEntryActivity]:
        # Get all entries for this event
        entry_ids = {eid for eid, evid in self._entry_event_map.items() if evid == event_id}
        links = [l for l in self._links if l.journal_entry_id in entry_ids]
        links.sort(key=lambda l: l.sort_order)
        return links

    async def link(self, entry_id: UUID, activity_id: UUID, sort_order: int = 0) -> JournalEntryActivity:
        link = JournalEntryActivity(
            id=self._next_id,
            journal_entry_id=entry_id,
            activity_id=activity_id,
            sort_order=sort_order,
        )
        self._next_id += 1
        self._links.append(link)
        return link

    async def unlink(self, entry_id: UUID, activity_id: UUID) -> bool:
        for i, link in enumerate(self._links):
            if link.journal_entry_id == entry_id and link.activity_id == activity_id:
                self._links.pop(i)
                return True
        return False

    async def reorder(self, entry_id: UUID, activity_ids: list[UUID]) -> None:
        for i, activity_id in enumerate(activity_ids):
            for link in self._links:
                if link.journal_entry_id == entry_id and link.activity_id == activity_id:
                    link.sort_order = i
                    break

    # --- Test helpers ---

    def clear(self) -> None:
        self._links.clear()
        self._next_id = 1

    def all(self) -> list[JournalEntryActivity]:
        return list(self._links)
