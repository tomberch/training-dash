"""
PostgreSQL implementation of UserRepo.

Uses SQLAlchemy async session for all database operations.
"""

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import User


class PostgresUserRepo:
    """
    PostgreSQL implementation of the UserRepo protocol.

    Requires an AsyncSession to be injected at construction time.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Fetch a user by ID. Returns None if not found."""
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by email (case-insensitive). Returns None if not found."""
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user with the given email exists."""
        result = await self._session.execute(select(func.count()).select_from(User).where(User.email == email))
        return (result.scalar() or 0) > 0

    async def list_all(self) -> list[User]:
        """List all users ordered by ID."""
        result = await self._session.execute(select(User).order_by(User.id))
        return list(result.scalars().all())

    async def list_pending_approval(self) -> list[User]:
        """List all users pending approval, ordered by created_at."""
        result = await self._session.execute(select(User).where(User.is_approved == False).order_by(User.created_at))
        return list(result.scalars().all())

    async def count(self) -> int:
        """Count total users."""
        result = await self._session.execute(select(func.count()).select_from(User))
        return result.scalar() or 0

    async def save(self, user: User) -> User:
        """
        Persist a user (insert or update).

        Returns the saved user with any DB-generated fields populated.
        """
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def delete(self, user_id: int) -> bool:
        """
        Delete a user by ID.

        CASCADE constraints handle related data cleanup.

        Returns True if deleted, False if not found.
        """
        # Check if user exists first
        user = await self.get_by_id(user_id)
        if user is None:
            return False

        await self._session.execute(sql_delete(User).where(User.id == user_id))
        await self._session.commit()
        return True
