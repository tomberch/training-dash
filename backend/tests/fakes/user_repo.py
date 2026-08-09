"""In-memory fake implementation of UserRepo for testing."""

from trainingdash.repositories.postgres.models import User


class FakeUserRepo:
    """
    In-memory fake implementation of UserRepo protocol.

    Stores users in a dict keyed by user ID.
    Auto-generates IDs for new users if not set.
    """

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._next_id = 1

    # --- Protocol methods ---

    async def get_by_id(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        email_lower = email.lower()
        for user in self._users.values():
            if user.email.lower() == email_lower:
                return user
        return None

    async def exists_by_email(self, email: str) -> bool:
        return await self.get_by_email(email) is not None

    async def list_all(self) -> list[User]:
        return sorted(self._users.values(), key=lambda u: u.id)

    async def list_pending_approval(self) -> list[User]:
        pending = [u for u in self._users.values() if not u.is_approved]
        return sorted(pending, key=lambda u: u.created_at or 0)

    async def count(self) -> int:
        return len(self._users)

    async def save(self, user: User) -> User:
        if user.id is None:
            user.id = self._next_id
            self._next_id += 1
        self._users[user.id] = user
        return user

    async def delete(self, user_id: int) -> bool:
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored users."""
        self._users.clear()
        self._next_id = 1

    def all(self) -> list[User]:
        """Return all stored users (for test assertions)."""
        return list(self._users.values())
