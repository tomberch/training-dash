"""Fake PacingCoefficientsRepo for testing."""

from datetime import UTC, datetime
from decimal import Decimal

from trainingdash.repositories.postgres.models import PacingCoefficients


class FakePacingCoefficientsRepo:
    """In-memory fake of PacingCoefficientsRepo for unit tests."""

    def __init__(self) -> None:
        self._coefficients: dict[tuple[int, int | None], PacingCoefficients] = {}
        self._next_id = 1

    def add(self, coefficients: PacingCoefficients) -> None:
        """Add coefficients directly (for test setup)."""
        if coefficients.id is None:
            coefficients.id = self._next_id
            self._next_id += 1
        key = (coefficients.user_id, coefficients.bike_id)
        self._coefficients[key] = coefficients

    async def get_for_user_bike(
        self,
        user_id: int,
        bike_id: int | None = None,
    ) -> PacingCoefficients | None:
        """Get with fallback chain: bike-specific → user default."""
        # Try bike-specific first
        if bike_id is not None:
            key = (user_id, bike_id)
            if key in self._coefficients:
                return self._coefficients[key]

        # Fall back to user default
        return await self.get_user_default(user_id)

    async def get_user_default(self, user_id: int) -> PacingCoefficients | None:
        """Get user default (bike_id=None)."""
        key = (user_id, None)
        return self._coefficients.get(key)

    async def get_for_bike(self, user_id: int, bike_id: int) -> PacingCoefficients | None:
        """Get bike-specific only (no fallback)."""
        key = (user_id, bike_id)
        return self._coefficients.get(key)

    async def list_for_user(self, user_id: int) -> list[PacingCoefficients]:
        """List all coefficients for a user."""
        results = [coef for (uid, _), coef in self._coefficients.items() if uid == user_id]
        # Sort by bike_id (None first)
        return sorted(results, key=lambda c: (c.bike_id is not None, c.bike_id or 0))

    async def save(self, coefficients: PacingCoefficients) -> PacingCoefficients:
        """Save coefficients."""
        if coefficients.id is None:
            coefficients.id = self._next_id
            self._next_id += 1
        coefficients.updated_at = datetime.now(UTC).replace(tzinfo=None)
        key = (coefficients.user_id, coefficients.bike_id)
        self._coefficients[key] = coefficients
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
        """Insert or update coefficients."""
        key = (user_id, bike_id)
        now = datetime.now(UTC).replace(tzinfo=None)

        if key in self._coefficients:
            coef = self._coefficients[key]
            coef.grade_power_intercept = Decimal(str(round(grade_power_intercept, 3)))
            coef.grade_power_slope = Decimal(str(round(grade_power_slope, 4)))
            coef.max_descent_speed_mps = Decimal(str(round(max_descent_speed_mps, 1)))
            coef.descent_power_multiplier = Decimal(str(round(descent_power_multiplier, 2)))
            coef.curvature_speed_coefficient = Decimal(str(round(curvature_speed_coefficient, 1)))
            coef.climb_sample_count = climb_sample_count
            coef.descent_sample_count = descent_sample_count
            coef.activity_count = activity_count
            coef.last_calibrated_at = now
            coef.updated_at = now
        else:
            coef = PacingCoefficients(
                id=self._next_id,
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
            self._next_id += 1
            self._coefficients[key] = coef

        return coef

    async def delete(self, user_id: int, bike_id: int | None) -> bool:
        """Delete coefficients."""
        key = (user_id, bike_id)
        if key in self._coefficients:
            del self._coefficients[key]
            return True
        return False
