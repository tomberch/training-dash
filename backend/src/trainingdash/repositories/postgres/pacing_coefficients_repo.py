"""
PostgreSQL implementation of PacingCoefficientsRepo.

Handles personalized pacing coefficients with fallback chain logic:
bike-specific → user default → global defaults (handled by caller).
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import PacingCoefficients


class PostgresPacingCoefficientsRepo:
    """
    PostgreSQL implementation of PacingCoefficientsRepo.

    Requires an AsyncSession to be injected at construction time.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user_bike(
        self,
        user_id: int,
        bike_id: int | None = None,
    ) -> PacingCoefficients | None:
        """
        Get pacing coefficients with fallback chain.

        Tries bike-specific first (if bike_id provided), then user default.
        Returns None if no coefficients found (caller should use global defaults).
        """
        # Try bike-specific first
        if bike_id is not None:
            bike_specific = await self.get_for_bike(user_id, bike_id)
            if bike_specific is not None:
                return bike_specific

        # Fall back to user default
        return await self.get_user_default(user_id)

    async def get_user_default(self, user_id: int) -> PacingCoefficients | None:
        """
        Get user's default coefficients (bike_id=NULL).

        Returns None if not yet created.
        """
        result = await self._session.execute(
            select(PacingCoefficients).where(
                PacingCoefficients.user_id == user_id,
                PacingCoefficients.bike_id.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_for_bike(self, user_id: int, bike_id: int) -> PacingCoefficients | None:
        """
        Get bike-specific coefficients only (no fallback).

        Returns None if no bike-specific coefficients exist.
        """
        result = await self._session.execute(
            select(PacingCoefficients).where(
                PacingCoefficients.user_id == user_id,
                PacingCoefficients.bike_id == bike_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[PacingCoefficients]:
        """
        List all coefficients for a user (default + all bikes).

        Ordered by bike_id (NULL first, then by bike_id).
        """
        result = await self._session.execute(
            select(PacingCoefficients)
            .where(PacingCoefficients.user_id == user_id)
            .order_by(PacingCoefficients.bike_id.nulls_first())
        )
        return list(result.scalars().all())

    async def save(self, coefficients: PacingCoefficients) -> PacingCoefficients:
        """
        Persist coefficients (insert or update).

        Returns the saved coefficients with any DB-generated fields populated.
        """
        # Use naive UTC datetime for TIMESTAMP WITHOUT TIME ZONE columns
        coefficients.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._session.add(coefficients)
        await self._session.commit()
        await self._session.refresh(coefficients)
        return coefficients

    async def upsert(
        self,
        user_id: int,
        bike_id: int | None,
        grade_power_intercept: float,
        grade_power_slope: float,
        max_descent_speed_mps: float,
        descent_power_multiplier: float,
        curvature_speed_coefficient: float,
        climb_sample_count: int,
        descent_sample_count: int,
        activity_count: int,
    ) -> PacingCoefficients:
        """
        Insert or update coefficients for a user/bike combination.

        Uses ON CONFLICT to atomically upsert. This is the preferred method
        for the learning pipeline to avoid race conditions.

        For bike_id=NULL (user default), uses the partial unique index.
        For bike_id != NULL (bike-specific), uses the unique constraint.
        """
        # Use naive UTC datetime for TIMESTAMP WITHOUT TIME ZONE columns
        now = datetime.now(UTC).replace(tzinfo=None)

        update_set = {
            "grade_power_intercept": Decimal(str(round(grade_power_intercept, 3))),
            "grade_power_slope": Decimal(str(round(grade_power_slope, 4))),
            "max_descent_speed_mps": Decimal(str(round(max_descent_speed_mps, 1))),
            "descent_power_multiplier": Decimal(str(round(descent_power_multiplier, 2))),
            "curvature_speed_coefficient": Decimal(str(round(curvature_speed_coefficient, 1))),
            "climb_sample_count": climb_sample_count,
            "descent_sample_count": descent_sample_count,
            "activity_count": activity_count,
            "last_calibrated_at": now,
            "updated_at": now,
        }

        stmt = insert(PacingCoefficients).values(
            user_id=user_id,
            bike_id=bike_id,
            grade_power_intercept=Decimal(str(round(grade_power_intercept, 3))),
            grade_power_slope=Decimal(str(round(grade_power_slope, 4))),
            max_descent_speed_mps=Decimal(str(round(max_descent_speed_mps, 1))),
            descent_power_multiplier=Decimal(str(round(descent_power_multiplier, 2))),
            curvature_speed_coefficient=Decimal(str(round(curvature_speed_coefficient, 1))),
            climb_sample_count=climb_sample_count,
            descent_sample_count=descent_sample_count,
            activity_count=activity_count,
            last_calibrated_at=now,
            created_at=now,
            updated_at=now,
        )

        # Use different conflict target based on bike_id:
        # - NULL bike_id: use partial unique index (ix_pacing_coefficients_user_default)
        # - Non-NULL bike_id: use unique constraint (uq_pacing_coefficients_user_bike)
        if bike_id is None:
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id"],
                index_where=PacingCoefficients.bike_id.is_(None),
                set_=update_set,
            )
        else:
            stmt = stmt.on_conflict_do_update(
                constraint="uq_pacing_coefficients_user_bike",
                set_=update_set,
            )

        stmt = stmt.returning(PacingCoefficients)

        result = await self._session.execute(stmt)
        await self._session.commit()

        row = result.scalar_one()
        # Refresh to get actual DB values after ON CONFLICT UPDATE
        await self._session.refresh(row)
        return row

    async def delete(self, user_id: int, bike_id: int | None) -> bool:
        """
        Delete coefficients for a user/bike combination.

        Returns True if deleted, False if not found.
        """
        if bike_id is None:
            # Delete user default
            stmt = delete(PacingCoefficients).where(
                PacingCoefficients.user_id == user_id,
                PacingCoefficients.bike_id.is_(None),
            )
        else:
            # Delete bike-specific
            stmt = delete(PacingCoefficients).where(
                PacingCoefficients.user_id == user_id,
                PacingCoefficients.bike_id == bike_id,
            )

        result = await self._session.execute(stmt)
        await self._session.commit()

        return result.rowcount > 0
