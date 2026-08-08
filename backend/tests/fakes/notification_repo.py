"""In-memory fake implementation of NotificationRepo for testing."""

from datetime import datetime, timezone
from uuid import UUID

from trainingdash.repositories.postgres.models import Notification


class FakeNotificationRepo:
    """
    In-memory fake implementation of NotificationRepo protocol.
    
    Stores notifications in a dict keyed by (user_id, notification_id).
    """

    def __init__(self) -> None:
        self._notifications: dict[tuple[int, UUID], Notification] = {}

    # --- Protocol methods ---

    async def list_for_user(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        user_notifications = [
            n for (uid, _), n in self._notifications.items() if uid == user_id
        ]
        # Sort by created_at descending
        user_notifications.sort(key=lambda n: n.created_at or 0, reverse=True)
        return user_notifications[offset : offset + limit]

    async def get_by_id(self, notification_id: UUID, user_id: int) -> Notification | None:
        return self._notifications.get((user_id, notification_id))

    async def mark_read(self, notification_id: UUID, user_id: int) -> bool:
        key = (user_id, notification_id)
        notification = self._notifications.get(key)
        if notification is None:
            return False
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return True

    async def mark_all_read(self, user_id: int) -> int:
        count = 0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for (uid, _), notification in self._notifications.items():
            if uid == user_id and notification.read_at is None:
                notification.read_at = now
                count += 1
        return count

    # --- Test helper methods ---

    def add(self, notification: Notification) -> None:
        """Add a notification (for test setup)."""
        if notification.user_id is None or notification.id is None:
            raise ValueError("Notification must have user_id and id")
        self._notifications[(notification.user_id, notification.id)] = notification

    def clear(self) -> None:
        """Clear all stored notifications."""
        self._notifications.clear()

    def all(self) -> list[Notification]:
        """Return all stored notifications (for test assertions)."""
        return list(self._notifications.values())
