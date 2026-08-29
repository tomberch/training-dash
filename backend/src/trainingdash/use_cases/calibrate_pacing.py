"""
Use case for calibrating personalized pacing coefficients.

Triggered after activity ingestion to update user/bike-specific
pacing model parameters from accumulated ride data.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.pacing_calibration import (
    MIN_ACTIVITIES,
    MIN_CLIMB_R_SQUARED,
    MIN_CLIMB_SAMPLES,
    MIN_DESCENT_SAMPLES,
    CalibrationResult,
    DescentSample,
    GradePowerSample,
    calibrate_coefficients,
    extract_climb_samples,
    extract_descent_samples,
    pedaling_average_power,
)
from trainingdash.domain.pacing_model import PacingCoefficients
from trainingdash.repositories.postgres.models import Activity, Record
from trainingdash.repositories.protocols import PacingCoefficientsRepo

logger = logging.getLogger(__name__)


@dataclass
class CalibrationStats:
    """Statistics from a calibration run."""

    activities_processed: int
    climb_samples: int
    descent_samples: int
    coefficients_updated: bool
    result: CalibrationResult | None
    message: str | None = None  # e.g. quality-gate rejection reason


class CalibratePacing:
    """
    Calibrate pacing coefficients from a user's activities.

    Queries all activities with measured power data, extracts grade-power
    relationships, and fits personalized coefficients via regression.
    """

    def __init__(
        self,
        db: AsyncSession,
        pacing_repo: PacingCoefficientsRepo,
    ) -> None:
        self._db = db
        self._pacing_repo = pacing_repo

    async def execute(
        self,
        user_id: int,
        bike_id: int | None = None,
    ) -> CalibrationStats:
        """
        Calibrate coefficients for a user, optionally for a specific bike.

        Args:
            user_id: User to calibrate for
            bike_id: If provided, calibrate bike-specific coefficients.
                     If None, calibrate user default (all bikes combined).

        Returns:
            CalibrationStats with results
        """
        # Fetch qualifying activities
        activities = await self._get_qualifying_activities(user_id, bike_id)

        if len(activities) < MIN_ACTIVITIES:
            logger.info(f"Not enough activities for calibration: {len(activities)} < {MIN_ACTIVITIES}")
            return CalibrationStats(
                activities_processed=len(activities),
                climb_samples=0,
                descent_samples=0,
                coefficients_updated=False,
                result=None,
            )

        # Accumulate samples from all activities
        all_climb_samples: list[GradePowerSample] = []
        all_descent_samples: list[DescentSample] = []

        for activity in activities:
            records = await self._get_records(str(activity.id))
            if not records or activity.avg_power_w is None:
                continue

            # Normalize by pedaling-time average power (ADR 0005): the
            # whole-ride average includes 0W coasting, which inflates the
            # intercept and flattens the slope of the grade-power fit.
            pedaling_avg = pedaling_average_power(records)
            if pedaling_avg is None:
                continue

            climb_samples = extract_climb_samples(records, pedaling_avg)
            descent_samples = extract_descent_samples(records, pedaling_avg)

            all_climb_samples.extend(climb_samples)
            all_descent_samples.extend(descent_samples)

        # Calibrate
        result = calibrate_coefficients(
            all_climb_samples,
            all_descent_samples,
            len(activities),
        )

        if result is None:
            # Distinguish gate rejection from insufficient data (ADR 0005)
            if (len(all_climb_samples) >= MIN_CLIMB_SAMPLES or len(all_descent_samples) >= MIN_DESCENT_SAMPLES) and len(
                activities
            ) >= MIN_ACTIVITIES:
                message = (
                    f"Fit quality below gate (R² < {MIN_CLIMB_R_SQUARED:.2f}): "
                    "grade-power relationship too noisy to trust. Keeping previously "
                    "stored coefficients. More/better ride data may help."
                )
            else:
                message = None  # plain insufficient-data case
            logger.info(
                f"Calibration not stored: climb={len(all_climb_samples)}, "
                f"descent={len(all_descent_samples)}: {message or 'insufficient data'}"
            )
            return CalibrationStats(
                activities_processed=len(activities),
                climb_samples=len(all_climb_samples),
                descent_samples=len(all_descent_samples),
                coefficients_updated=False,
                result=None,
                message=message,
            )

        # Save to database
        await self._pacing_repo.upsert(
            user_id,
            PacingCoefficients(
                grade_power_intercept=result.grade_power_intercept,
                grade_power_slope=result.grade_power_slope,
                max_descent_speed_mps=result.max_descent_speed_mps,
                descent_power_multiplier=result.descent_power_multiplier,
                curvature_speed_coefficient=result.curvature_speed_coefficient,
                climb_sample_count=result.climb_sample_count,
                descent_sample_count=result.descent_sample_count,
                activity_count=result.activity_count,
            ),
        )

        logger.info(
            f"Calibrated pacing coefficients for user={user_id} bike={bike_id}: "
            f"intercept={result.grade_power_intercept:.3f}, "
            f"slope={result.grade_power_slope:.4f}, "
            f"max_descent={result.max_descent_speed_mps:.1f}m/s, "
            f"R²={result.climb_r_squared:.3f}"
        )

        return CalibrationStats(
            activities_processed=len(activities),
            climb_samples=len(all_climb_samples),
            descent_samples=len(all_descent_samples),
            coefficients_updated=True,
            result=result,
        )

    async def execute_for_all_bikes(
        self,
        user_id: int,
    ) -> dict[int | None, CalibrationStats]:
        """
        Calibrate coefficients for all user's bikes plus a user default.

        Returns:
            Dict mapping bike_id (or None for default) to CalibrationStats
        """
        results: dict[int | None, CalibrationStats] = {}

        # First, calibrate user default (all activities, no bike filter)
        results[None] = await self.execute(user_id, bike_id=None)

        # Get distinct bikes with qualifying activities
        bike_ids = await self._get_bikes_with_activities(user_id)

        for bike_id in bike_ids:
            results[bike_id] = await self.execute(user_id, bike_id=bike_id)

        return results

    async def _get_qualifying_activities(
        self,
        user_id: int,
        bike_id: int | None,
    ) -> list[Activity]:
        """Get activities that qualify for calibration."""
        query = (
            select(Activity)
            .where(
                Activity.user_id == user_id,
                Activity.avg_power_w.isnot(None),
                Activity.total_distance_m > 5000,  # At least 5km
                Activity.elapsed_time_s > 1200,  # At least 20 minutes
                Activity.power_source == "measured",  # Only actual power meters
                Activity.elevation_gain_m > 100,  # Must have some climbing
            )
            .order_by(Activity.started_at.desc())
        )

        if bike_id is not None:
            query = query.where(Activity.bike_id == bike_id)

        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def _get_records(self, activity_id: str) -> list[Record]:
        """Get records for an activity."""
        result = await self._db.execute(
            select(Record).where(Record.activity_id == activity_id).order_by(Record.distance_m)
        )
        return list(result.scalars().all())

    async def _get_bikes_with_activities(self, user_id: int) -> list[int]:
        """Get bike IDs that have qualifying activities."""
        from sqlalchemy import distinct

        result = await self._db.execute(
            select(distinct(Activity.bike_id)).where(
                Activity.user_id == user_id,
                Activity.bike_id.isnot(None),
                Activity.avg_power_w.isnot(None),
                Activity.power_source == "measured",
                Activity.elevation_gain_m > 100,
            )
        )
        return [row[0] for row in result.fetchall() if row[0] is not None]
