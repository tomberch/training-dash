"""
Use case for batch linking activities to a ride event.

Activities are linked via journal entries - if no entry exists for an
activity's date, one is auto-created.
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from trainingdash.repositories.postgres.models import JournalEntry
from trainingdash.repositories.protocols import (
    ActivityRepo,
    JournalEntryActivityRepo,
    JournalEntryRepo,
    RideEventRepo,
)


@dataclass
class LinkedActivity:
    """Result of linking a single activity."""

    link_id: int
    journal_entry_id: UUID
    activity_id: UUID
    sort_order: int


@dataclass
class BatchLinkResult:
    """Result of the batch link operation."""

    linked: list[LinkedActivity]
    skipped_count: int  # Activities not owned by user or not found


class BatchLinkActivities:
    """
    Batch link activities to a ride event.

    For each activity:
    1. Verify the user owns the activity
    2. Find or create a journal entry for the activity's date
    3. Link the activity to the journal entry

    Activities not owned by the user are silently skipped.
    """

    def __init__(
        self,
        event_repo: RideEventRepo,
        entry_repo: JournalEntryRepo,
        activity_repo: ActivityRepo,
        activity_link_repo: JournalEntryActivityRepo,
    ):
        self._event_repo = event_repo
        self._entry_repo = entry_repo
        self._activity_repo = activity_repo
        self._activity_link_repo = activity_link_repo

    async def execute(
        self,
        user_id: int,
        event_id: UUID,
        activity_ids: list[UUID],
    ) -> BatchLinkResult:
        """
        Link multiple activities to an event.

        Args:
            user_id: ID of the user performing the operation
            event_id: ID of the ride event to link to
            activity_ids: List of activity IDs to link

        Returns:
            BatchLinkResult with linked activities and skip count

        Raises:
            ValueError: If event not found or not owned by user
        """
        # Verify event ownership
        event = await self._event_repo.get_by_id(event_id, user_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found")

        # Cache entries for this event to avoid repeated queries
        entries = await self._entry_repo.list_for_event(event_id)
        entries_by_date: dict[date, JournalEntry] = {e.entry_date: e for e in entries}

        linked: list[LinkedActivity] = []
        skipped = 0

        for activity_id in activity_ids:
            # Verify user owns the activity
            activity = await self._activity_repo.get_by_id(activity_id, user_id)
            if activity is None:
                skipped += 1
                continue

            # Determine the date for this activity
            activity_date = activity.started_at.date() if activity.started_at else event.start_date

            # Find or create journal entry for this date
            entry = entries_by_date.get(activity_date)
            if entry is None:
                entry = JournalEntry(
                    id=uuid4(),
                    ride_event_id=event_id,
                    entry_date=activity_date,
                )
                entry = await self._entry_repo.save(entry)
                entries_by_date[activity_date] = entry

            # Link activity to entry
            link = await self._activity_link_repo.link(entry.id, activity_id, sort_order=0)

            linked.append(
                LinkedActivity(
                    link_id=link.id,
                    journal_entry_id=link.journal_entry_id,
                    activity_id=link.activity_id,
                    sort_order=link.sort_order,
                )
            )

        return BatchLinkResult(linked=linked, skipped_count=skipped)
