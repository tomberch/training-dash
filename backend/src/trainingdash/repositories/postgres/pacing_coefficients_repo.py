"""
PostgreSQL implementation of PacingCoefficientsRepo.

The repository is the adapter at the DB seam (ADR 0004): it translates
between the domain PacingCoefficients (pacing_model.py) and the SQLAlchemy
row. Callers never see ORM types.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.pacing_model import PacingCoefficients
from trainingdash.repositories.postgres.models import PacingCoefficients as PacingCoefficientsModel


def _to_model(coef: PacingCoefficients) -> PacingCoefficientsModel:
    """Translate a domain PacingCoefficients into an ORM row (partial: key fields only)."""
    return PacingCoefficientsModel(
        bike_id=coef.bike_id,
        grade_power_intercept=Decimal(str(coef.grade_power_intercept)),
        grade_power_slope=Decimal(str(coef.grade_power_slope)),
        max_descent_speed_mps=Decimal(str(coef.max_descent_speed_mps)),
        descent_power_multiplier=Decimal(str(coef.descent_power_multiplier)),
        curvature_speed_coefficient=Decimal(str(coef.curvature_speed_coefficient)),
        climb_sample_count=coef.climb_sample_count,
        descent_sample_count=coef.descent_sample_count,
        activity_count=coef.activity_count,
        last_calibrated_at=coef.last_calibrated_at,
    )


def _from_model(model: PacingCoefficientsModel) -> PacingCoefficients:
    """Translate an ORM row into a domain PacingCoefficients."""
    return PacingCoefficients(
        grade_power_intercept=float(model.grade_power_intercept),
        grade_power_slope=float(model.grade_power_slope),
        max_descent_speed_mps=float(model.max_descent_speed_mps),
        descent_power_multiplier=float(model.descent_power_multiplier),
        curvature_speed_coefficient=float(model.curvature_speed_coefficient),
        bike_id=model.bike_id,
        climb_sample_count=model.climb_sample_count,
        descent_sample_count=model.descent_sample_count,
        activity_count=model.activity_count,
        last_calibrated_at=model.last_calibrated_at,
    )


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
            select(PacingCoefficientsModel).where(
                PacingCoefficientsModel.user_id == user_id,
                PacingCoefficientsModel.bike_id.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        return _from_model(row) if row is not None else None

    async def get_for_bike(self, user_id: int, bike_id: int) -> PacingCoefficients | None:
        """
        Get bike-specific coefficients only (no fallback).

        Returns None if no bike-specific coefficients exist.
        """
        result = await self._session.execute(
            select(PacingCoefficientsModel).where(
                PacingCoefficientsModel.user_id == user_id,
                PacingCoefficientsModel.bike_id == bike_id,
            )
        )
        row = result.scalar_one_or_none()
        return _from_model(row) if row is not None else None

    async def list_for_user(self, user_id: int) -> list[PacingCoefficients]:
        """
        List all coefficients for a user (default + all bikes).

        Ordered by bike_id (NULL first, then by bike_id).
        """
        result = await self._session.execute(
            select(PacingCoefficientsModel)
            .where(PacingCoefficientsModel.user_id == user_id)
            .order_by(PacingCoefficientsModel.bike_id.nulls_first())
        )
        return [_from_model(row) for row in result.scalars().all()]

    async def save(self, coefficients: PacingCoefficients) -> PacingCoefficients:
        """
        Persist coefficients (insert or update).

        Requires coefficients.user_id to be set. Returns the saved
        coefficients with any DB-generated fields populated.
        """
        if coefficients.user_id is None:
            raise ValueError("user_id is required to save coefficients")

        row = _to_model(coefficients)
        row.user_id = coefficients.user_id
        # Use naive UTC datetime for TIMESTAMP WITHOUT TIME ZONE columns
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _from_model(row)

    async def upsert(
        self,
        user_id: int,
        coefficients: PacingCoefficients,
    ) -> PacingCoefficients:
        """
        Insert or update coefficients for a user/bike combination.

        Uses ON CONFLICT to atomically upsert. This is the preferred method
        for the learning pipeline to avoid race conditions.

        For bike_id=None (user default), uses the partial unique index.
        For bike_id != None (bike-specific), uses the unique constraint.
        """
        bike_id = coefficients.bike_id
        # Use naive UTC datetime for TIMESTAMP WITHOUT TIME ZONE columns
        now = datetime.now(UTC).replace(tzinfo=None)

        update_set = {
            "grade_power_intercept": Decimal(str(round(coefficients.grade_power_intercept, 3))),
            "grade_power_slope": Decimal(str(round(coefficients.grade_power_slope, 4))),
            "max_descent_speed_mps": Decimal(str(round(coefficients.max_descent_speed_mps, 1))),
            "descent_power_multiplier": Decimal(str(round(coefficients.descent_power_multiplier, 2))),
            "curvature_speed_coefficient": Decimal(str(round(coefficients.curvature_speed_coefficient, 1))),
            "climb_sample_count": coefficients.climb_sample_count,
            "descent_sample_count": coefficients.descent_sample_count,
            "activity_count": coefficients.activity_count,
            "last_calibrated_at": now,
            "updated_at": now,
        }

        stmt = insert(PacingCoefficientsModel).values(
            user_id=user_id,
            bike_id=bike_id,
            grade_power_intercept=Decimal(str(round(coefficients.grade_power_intercept, 3))),
            grade_power_slope=Decimal(str(round(coefficients.grade_power_slope, 4))),
            max_descent_speed_mps=Decimal(str(round(coefficients.max_descent_speed_mps, 1))),
            descent_power_multiplier=Decimal(str(round(coefficients.descent_power_multiplier, 2))),
            curvature_speed_coefficient=Decimal(str(round(coefficients.curvature_speed_coefficient, 1))),
            climb_sample_count=coefficients.climb_sample_count,
            descent_sample_count=coefficients.descent_sample_count,
            activity_count=coefficients.activity_count,
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
                index_where=PacingCoefficientsModel.bike_id.is_(None),
                set_=update_set,
            )
        else:
            stmt = stmt.on_conflict_do_update(
                constraint="uq_pacing_coefficients_user_bike",
                set_=update_set,
            )

        stmt = stmt.returning(PacingCoefficientsModel)

        result = await self._session.execute(stmt)
        await self._session.commit()

        row = result.scalar_one()
        # Refresh to get actual DB values after ON CONFLICT UPDATE
        await self._session.refresh(row)
        return _from_model(row)

    async def delete(self, user_id: int, bike_id: int | None) -> bool:
        """
        Delete coefficients for a user/bike combination.

        Returns True if deleted, False if not found.
        """
        if bike_id is None:
            # Delete user default
            stmt = delete(PacingCoefficientsModel).where(
                PacingCoefficientsModel.user_id == user_id,
                PacingCoefficientsModel.bike_id.is_(None),
            )
        else:
            # Delete bike-specific
            stmt = delete(PacingCoefficientsModel).where(
                PacingCoefficientsModel.user_id == user_id,
                PacingCoefficientsModel.bike_id == bike_id,
            )

        result = await self._session.execute(stmt)
        await self._session.commit()

        return result.rowcount > 0
