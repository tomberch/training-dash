"""
PostgreSQL implementation of RideEvent repositories.

Uses SQLAlchemy async session for all database operations.
"""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import (
    Activity,
    JournalEntry,
    JournalEntryActivity,
    RideEvent,
    RideEventLink,
    RideEventMedia,
)


class PostgresRideEventRepo:
    """PostgreSQL implementation of the RideEventRepo protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, event_id: UUID, user_id: int) -> RideEvent | None:
        """Fetch a ride event by ID, scoped to user."""
        result = await self._session.execute(
            select(RideEvent).where(
                RideEvent.id == event_id,
                RideEvent.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: int,
        event_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RideEvent]:
        """List ride events for a user, ordered by start_date descending."""
        query = select(RideEvent).where(RideEvent.user_id == user_id)

        if event_type is not None:
            query = query.where(RideEvent.event_type == event_type)

        query = query.order_by(RideEvent.start_date.desc()).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_for_user(self, user_id: int, event_type: str | None = None) -> int:
        """Count total ride events for a user."""
        query = select(func.count(RideEvent.id)).where(RideEvent.user_id == user_id)
        if event_type is not None:
            query = query.where(RideEvent.event_type == event_type)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def save(self, event: RideEvent) -> RideEvent:
        """Persist a ride event (insert or update)."""
        self._session.add(event)
        await self._session.commit()
        await self._session.refresh(event)
        return event

    async def delete(self, event_id: UUID, user_id: int) -> bool:
        """Delete a ride event owned by the given user."""
        event = await self.get_by_id(event_id, user_id)
        if event is None:
            return False

        # Unlink activities from this event (SET NULL handled by FK, but explicit for clarity)
        await self._session.execute(
            Activity.__table__.update().where(Activity.ride_event_id == event_id).values(ride_event_id=None)
        )

        # Delete the event (cascades journal entries, media, links)
        await self._session.execute(delete(RideEvent).where(RideEvent.id == event_id))
        await self._session.commit()
        return True


class PostgresJournalEntryRepo:
    """PostgreSQL implementation of the JournalEntryRepo protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, entry_id: UUID, user_id: int) -> JournalEntry | None:
        """Fetch a journal entry by ID, scoped to user via event ownership."""
        result = await self._session.execute(
            select(JournalEntry)
            .join(RideEvent, JournalEntry.ride_event_id == RideEvent.id)
            .where(
                JournalEntry.id == entry_id,
                RideEvent.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_event(self, event_id: UUID) -> list[JournalEntry]:
        """List journal entries for an event, ordered by entry_date ascending."""
        result = await self._session.execute(
            select(JournalEntry).where(JournalEntry.ride_event_id == event_id).order_by(JournalEntry.entry_date.asc())
        )
        return list(result.scalars().all())

    async def save(self, entry: JournalEntry) -> JournalEntry:
        """Persist a journal entry (insert or update)."""
        self._session.add(entry)
        await self._session.commit()
        await self._session.refresh(entry)
        return entry

    async def delete(self, entry_id: UUID, user_id: int) -> bool:
        """Delete a journal entry (user must own the parent event)."""
        entry = await self.get_by_id(entry_id, user_id)
        if entry is None:
            return False

        await self._session.execute(delete(JournalEntry).where(JournalEntry.id == entry_id))
        await self._session.commit()
        return True


class PostgresRideEventMediaRepo:
    """PostgreSQL implementation of the RideEventMediaRepo protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, media_id: UUID, user_id: int) -> RideEventMedia | None:
        """Fetch media by ID, scoped to user via event/entry ownership."""
        # First, just fetch the media record
        result = await self._session.execute(select(RideEventMedia).where(RideEventMedia.id == media_id))
        media = result.scalar_one_or_none()
        if media is None:
            return None

        # Verify ownership
        if media.ride_event_id is not None:
            event_result = await self._session.execute(
                select(RideEvent).where(
                    RideEvent.id == media.ride_event_id,
                    RideEvent.user_id == user_id,
                )
            )
            if event_result.scalar_one_or_none() is None:
                return None
        elif media.journal_entry_id is not None:
            entry_result = await self._session.execute(
                select(JournalEntry)
                .join(RideEvent, JournalEntry.ride_event_id == RideEvent.id)
                .where(
                    JournalEntry.id == media.journal_entry_id,
                    RideEvent.user_id == user_id,
                )
            )
            if entry_result.scalar_one_or_none() is None:
                return None

        return media

    async def list_for_event(self, event_id: UUID) -> list[RideEventMedia]:
        """List all media directly attached to an event."""
        result = await self._session.execute(
            select(RideEventMedia)
            .where(RideEventMedia.ride_event_id == event_id)
            .order_by(RideEventMedia.sort_order.asc())
        )
        return list(result.scalars().all())

    async def list_for_entry(self, entry_id: UUID) -> list[RideEventMedia]:
        """List all media attached to a journal entry."""
        result = await self._session.execute(
            select(RideEventMedia)
            .where(RideEventMedia.journal_entry_id == entry_id)
            .order_by(RideEventMedia.sort_order.asc())
        )
        return list(result.scalars().all())

    async def save(self, media: RideEventMedia) -> RideEventMedia:
        """Persist media (insert or update)."""
        self._session.add(media)
        await self._session.commit()
        await self._session.refresh(media)
        return media

    async def delete(self, media_id: UUID, user_id: int) -> bool:
        """Delete media. Returns True if deleted."""
        media = await self.get_by_id(media_id, user_id)
        if media is None:
            return False

        await self._session.execute(delete(RideEventMedia).where(RideEventMedia.id == media_id))
        await self._session.commit()
        return True


class PostgresRideEventLinkRepo:
    """PostgreSQL implementation of the RideEventLinkRepo protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, link_id: UUID, user_id: int) -> RideEventLink | None:
        """Fetch link by ID, scoped to user via event/entry ownership."""
        result = await self._session.execute(select(RideEventLink).where(RideEventLink.id == link_id))
        link = result.scalar_one_or_none()
        if link is None:
            return None

        # Verify ownership
        if link.ride_event_id is not None:
            event_result = await self._session.execute(
                select(RideEvent).where(
                    RideEvent.id == link.ride_event_id,
                    RideEvent.user_id == user_id,
                )
            )
            if event_result.scalar_one_or_none() is None:
                return None
        elif link.journal_entry_id is not None:
            entry_result = await self._session.execute(
                select(JournalEntry)
                .join(RideEvent, JournalEntry.ride_event_id == RideEvent.id)
                .where(
                    JournalEntry.id == link.journal_entry_id,
                    RideEvent.user_id == user_id,
                )
            )
            if entry_result.scalar_one_or_none() is None:
                return None

        return link

    async def list_for_event(self, event_id: UUID) -> list[RideEventLink]:
        """List all links directly attached to an event."""
        result = await self._session.execute(
            select(RideEventLink)
            .where(RideEventLink.ride_event_id == event_id)
            .order_by(RideEventLink.sort_order.asc())
        )
        return list(result.scalars().all())

    async def list_for_entry(self, entry_id: UUID) -> list[RideEventLink]:
        """List all links attached to a journal entry."""
        result = await self._session.execute(
            select(RideEventLink)
            .where(RideEventLink.journal_entry_id == entry_id)
            .order_by(RideEventLink.sort_order.asc())
        )
        return list(result.scalars().all())

    async def save(self, link: RideEventLink) -> RideEventLink:
        """Persist link (insert or update)."""
        self._session.add(link)
        await self._session.commit()
        await self._session.refresh(link)
        return link

    async def delete(self, link_id: UUID, user_id: int) -> bool:
        """Delete link. Returns True if deleted."""
        link = await self.get_by_id(link_id, user_id)
        if link is None:
            return False

        await self._session.execute(delete(RideEventLink).where(RideEventLink.id == link_id))
        await self._session.commit()
        return True


class PostgresJournalEntryActivityRepo:
    """PostgreSQL implementation of the JournalEntryActivityRepo protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_entry(self, entry_id: UUID) -> list[JournalEntryActivity]:
        """List activity links for a journal entry, ordered by sort_order."""
        result = await self._session.execute(
            select(JournalEntryActivity)
            .where(JournalEntryActivity.journal_entry_id == entry_id)
            .order_by(JournalEntryActivity.sort_order.asc())
        )
        return list(result.scalars().all())

    async def list_for_event(self, event_id: UUID) -> list[JournalEntryActivity]:
        """List all activity links across all entries in an event."""
        result = await self._session.execute(
            select(JournalEntryActivity)
            .join(JournalEntry, JournalEntryActivity.journal_entry_id == JournalEntry.id)
            .where(JournalEntry.ride_event_id == event_id)
            .order_by(JournalEntry.entry_date.asc(), JournalEntryActivity.sort_order.asc())
        )
        return list(result.scalars().all())

    async def link(self, entry_id: UUID, activity_id: UUID, sort_order: int = 0) -> JournalEntryActivity:
        """Link an activity to a journal entry."""
        link = JournalEntryActivity(
            journal_entry_id=entry_id,
            activity_id=activity_id,
            sort_order=sort_order,
        )
        self._session.add(link)
        await self._session.commit()
        await self._session.refresh(link)
        return link

    async def unlink(self, entry_id: UUID, activity_id: UUID) -> bool:
        """Unlink an activity from a journal entry."""
        result = await self._session.execute(
            delete(JournalEntryActivity).where(
                JournalEntryActivity.journal_entry_id == entry_id,
                JournalEntryActivity.activity_id == activity_id,
            )
        )
        await self._session.commit()
        return result.rowcount > 0

    async def reorder(self, entry_id: UUID, activity_ids: list[UUID]) -> None:
        """Reorder activities in an entry based on the provided ID list."""
        for i, activity_id in enumerate(activity_ids):
            await self._session.execute(
                JournalEntryActivity.__table__.update()
                .where(
                    JournalEntryActivity.journal_entry_id == entry_id,
                    JournalEntryActivity.activity_id == activity_id,
                )
                .values(sort_order=i)
            )
        await self._session.commit()
