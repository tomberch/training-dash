"""
PostgreSQL implementation of RouteRepo.

Uses SQLAlchemy async session for all database operations.
Route matching uses PostGIS spatial operations that cannot be easily abstracted.
"""

from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Route


class PostgresRouteRepo:
    """
    PostgreSQL implementation of the RouteRepo protocol.
    
    Note: The find_or_create operation in route_matching.py uses complex
    PostGIS spatial queries (ST_HausdorffDistance, ST_Simplify) that are
    tightly coupled to PostgreSQL. Those remain in route_matching.py.
    
    This repo handles simpler route operations.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def get_by_id(self, route_id: int) -> Route | None:
        """Fetch a route by ID."""
        result = await self._session.execute(
            select(Route).where(Route.id == route_id)
        )
        return result.scalar_one_or_none()
    
    async def list_for_user(self, user_id: int) -> list[Route]:
        """List all routes for a user."""
        result = await self._session.execute(
            select(Route)
            .where(Route.user_id == user_id)
            .order_by(Route.ride_count.desc())
        )
        return list(result.scalars().all())
    
    async def increment_ride_count(self, route_id: int) -> None:
        """Increment the ride count for a route."""
        await self._session.execute(
            sql_text("UPDATE routes SET ride_count = ride_count + 1 WHERE id = :rid"),
            {"rid": route_id},
        )
    
    async def decrement_ride_count(self, route_id: int) -> None:
        """Decrement the ride count for a route."""
        await self._session.execute(
            sql_text("UPDATE routes SET ride_count = ride_count - 1 WHERE id = :rid"),
            {"rid": route_id},
        )
    
    async def delete(self, route_id: int) -> bool:
        """Delete a route. Returns True if deleted."""
        result = await self._session.execute(
            sql_text("DELETE FROM routes WHERE id = :rid RETURNING id"),
            {"rid": route_id},
        )
        return result.scalar_one_or_none() is not None
