"""In-memory fake implementation of RecordRepo for testing."""

from uuid import UUID

from trainingdash.repositories.postgres.models import Record


class FakeRecordRepo:
    """
    In-memory fake implementation of RecordRepo protocol.

    Stores records in a dict keyed by activity_id.
    Provides inspection methods for test assertions.
    """

    def __init__(self) -> None:
        self._records: dict[UUID, list[Record]] = {}
        self._next_id: int = 1

    # --- Protocol methods ---

    async def list_for_activity(self, activity_id: UUID) -> list[Record]:
        records = self._records.get(activity_id, [])
        # Sort by timestamp ascending
        return sorted(records, key=lambda r: r.timestamp)

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored records."""
        self._records.clear()
        self._next_id = 1

    def all(self) -> list[Record]:
        """Return all stored records (for test assertions)."""
        all_records = []
        for records in self._records.values():
            all_records.extend(records)
        return all_records

    def add(self, record: Record) -> Record:
        """Synchronous helper to add a record for test setup."""
        if record.activity_id is None:
            raise ValueError("Record must have an activity_id")
        if record.id is None:
            record.id = self._next_id
            self._next_id += 1
        if record.activity_id not in self._records:
            self._records[record.activity_id] = []
        self._records[record.activity_id].append(record)
        return record

    def add_many(self, records: list[Record]) -> list[Record]:
        """Synchronous helper to add multiple records for test setup."""
        for record in records:
            self.add(record)
        return records
