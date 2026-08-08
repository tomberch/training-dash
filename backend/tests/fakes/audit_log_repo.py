"""In-memory fake implementation of AuditLogRepo for testing."""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class AuditLogEntry:
    """Simple data class representing an audit log entry."""
    admin_id: int
    action: str
    target_user_id: int | None
    details: str | None
    created_at: datetime


class FakeAuditLogRepo:
    """
    In-memory fake implementation of AuditLogRepo protocol.
    
    Stores audit entries in a list (append-only like real audit log).
    """

    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []

    # --- Protocol methods ---

    async def log(
        self,
        admin_id: int,
        action: str,
        target_user_id: int | None = None,
        details: str | None = None,
    ) -> None:
        entry = AuditLogEntry(
            admin_id=admin_id,
            action=action,
            target_user_id=target_user_id,
            details=details,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self._entries.append(entry)

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored entries."""
        self._entries.clear()

    def all(self) -> list[AuditLogEntry]:
        """Return all stored entries (for test assertions)."""
        return list(self._entries)

    def find_by_action(self, action: str) -> list[AuditLogEntry]:
        """Find entries by action type."""
        return [e for e in self._entries if e.action == action]

    def find_by_admin(self, admin_id: int) -> list[AuditLogEntry]:
        """Find entries by admin ID."""
        return [e for e in self._entries if e.admin_id == admin_id]
