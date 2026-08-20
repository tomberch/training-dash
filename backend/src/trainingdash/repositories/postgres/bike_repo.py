"""
PostgreSQL implementation of BikeRepo.

Uses SQLAlchemy async session for all database operations.
"""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Bike


class PostgresBikeRepo:
    """
    PostgreSQL implementation of the BikeRepo protocol.

    Requires an AsyncSession to be injected at construction time.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, bike_id: int, user_id: int) -> Bike | None:
        """
        Fetch a bike by ID, scoped to user.

        Returns None if not found or not owned by user.
        """
        # Use populate_existing to bypass identity map cache and get fresh data
        result = await self._session.execute(
            select(Bike)
            .where(
                Bike.id == bike_id,
                Bike.user_id == user_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int, include_retired: bool = False) -> list[Bike]:
        """
        List bikes for a user, ordered by name.

        Args:
            user_id: Owner's user ID
            include_retired: If True, include retired bikes

        Returns:
            List of Bike objects
        """
        query = select(Bike).where(Bike.user_id == user_id)

        if not include_retired:
            query = query.where(Bike.retired_at.is_(None))

        result = await self._session.execute(query.order_by(Bike.name))
        return list(result.scalars().all())

    async def get_default_for_user(self, user_id: int) -> Bike | None:
        """
        Get the user's default bike.

        Returns None if no default bike is set or if the default is retired.
        """
        result = await self._session.execute(
            select(Bike).where(
                Bike.user_id == user_id,
                Bike.is_default.is_(True),
                Bike.retired_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def save(self, bike: Bike) -> Bike:
        """
        Persist a bike (insert or update).

        Returns the saved bike with any DB-generated fields populated.
        """
        self._session.add(bike)
        await self._session.commit()
        await self._session.refresh(bike)
        return bike

    async def update_distance(self, bike_id: int, user_id: int, delta_m: float) -> None:
        """
        Update a bike's total_distance_m by adding delta_m.

        Args:
            bike_id: Bike ID
            user_id: Owner's user ID (for security scoping)
            delta_m: Distance to add (can be negative for corrections)
        """
        await self._session.execute(
            update(Bike)
            .where(Bike.id == bike_id, Bike.user_id == user_id)
            .values(total_distance_m=Bike.total_distance_m + delta_m)
        )
        await self._session.commit()

    async def set_default(self, user_id: int, bike_id: int) -> None:
        """
        Set a bike as the user's default.

        Clears any existing default for the user first.
        The bike must be non-retired and owned by the user.
        """
        # Clear existing default
        await self._session.execute(
            update(Bike)
            .where(Bike.user_id == user_id, Bike.is_default.is_(True))
            .values(is_default=False)
        )

        # Set new default
        await self._session.execute(
            update(Bike)
            .where(
                Bike.id == bike_id,
                Bike.user_id == user_id,
                Bike.retired_at.is_(None),
            )
            .values(is_default=True)
        )
        await self._session.commit()

    async def clear_default(self, user_id: int) -> None:
        """
        Clear the user's default bike (no bike is default).
        """
        await self._session.execute(
            update(Bike)
            .where(Bike.user_id == user_id, Bike.is_default.is_(True))
            .values(is_default=False)
        )
        await self._session.commit()

    async def retire(self, bike_id: int, user_id: int) -> bool:
        """
        Retire a bike (soft delete).

        Sets retired_at timestamp. If the bike was default, clears default.

        Returns True if retired, False if not found.
        """
        # Get the bike to check if it exists and is owned by user
        bike = await self.get_by_id(bike_id, user_id)
        if bike is None:
            return False

        # If already retired, nothing to do
        if bike.retired_at is not None:
            return True

        # Clear default if this was the default bike
        if bike.is_default:
            bike.is_default = False

        bike.retired_at = datetime.now()
        await self._session.commit()
        return True
