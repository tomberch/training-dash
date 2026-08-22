"""
FetchActivityWeather use case — fetch weather data for activities pending weather.

This use case:
1. Finds activities with weather_status='pending'
2. Fetches weather from Open-Meteo for each activity
3. Stores hourly weather snapshots in activity_weather table
4. Re-runs aero estimation if weather fetch succeeds
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from trainingdash.domain.aero_estimation import (
    ActivityRecord,
    WeatherSnapshot,
    WeatherStatus,
    calculate_air_density,
    check_estimation_requirements,
    estimate_cda_crr,
    prepare_data_points,
)
from trainingdash.integrations.weather import fetch_activity_weather
from trainingdash.repositories.postgres.models import (
    Activity,
    ActivityWeather,
    Bike,
    Record,
    User,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class FetchWeatherResult:
    """Result of weather fetch operation."""

    activities_processed: int = 0
    weather_fetched: int = 0
    aero_estimated: int = 0
    errors: list[str] | None = None


class FetchActivityWeather:
    """
    Use case for fetching weather data and running aero estimation.

    Processes activities marked with weather_status='pending', fetches
    historical weather from Open-Meteo, and stores it for aero estimation.

    Example usage:
        use_case = FetchActivityWeather(db)
        result = await use_case.execute(user_id=1)
        # Or process a single activity:
        result = await use_case.execute_single(activity_id=uuid)
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def execute(self, user_id: int, limit: int = 10) -> FetchWeatherResult:
        """
        Fetch weather for all pending activities for a user.

        Args:
            user_id: User to process activities for
            limit: Maximum activities to process in one run

        Returns:
            FetchWeatherResult with counts and any errors
        """
        from sqlalchemy import or_

        result = FetchWeatherResult(errors=[])

        # Find activities pending weather fetch
        # Include NULL status (historical activities) and 'pending' status
        query = (
            select(Activity)
            .where(
                Activity.user_id == user_id,
                or_(
                    Activity.weather_status == WeatherStatus.PENDING,
                    Activity.weather_status.is_(None),
                ),
            )
            .order_by(Activity.started_at.desc())
            .limit(limit)
        )
        activities = (await self._db.execute(query)).scalars().all()

        result.activities_processed = len(activities)

        for activity in activities:
            try:
                success = await self._process_activity(activity)
                if success:
                    result.weather_fetched += 1
                    # Try aero estimation
                    if await self._run_aero_estimation(activity):
                        result.aero_estimated += 1
            except Exception as e:
                logger.exception(f"Error processing activity {activity.id}")
                result.errors.append(f"{activity.id}: {e}")

        await self._db.commit()
        return result

    async def execute_single(self, activity_id: UUID) -> FetchWeatherResult:
        """
        Fetch weather for a single activity.

        Args:
            activity_id: Activity UUID to process

        Returns:
            FetchWeatherResult with counts
        """
        result = FetchWeatherResult(errors=[])

        activity = await self._db.get(Activity, activity_id)
        if not activity:
            result.errors = [f"Activity {activity_id} not found"]
            return result

        result.activities_processed = 1

        try:
            success = await self._process_activity(activity)
            if success:
                result.weather_fetched = 1
                if await self._run_aero_estimation(activity):
                    result.aero_estimated = 1
        except Exception as e:
            logger.exception(f"Error processing activity {activity_id}")
            result.errors = [str(e)]

        await self._db.commit()
        return result

    async def _process_activity(self, activity: Activity) -> bool:
        """Fetch and store weather for a single activity."""
        # Get first GPS point for location
        record_query = (
            select(Record)
            .where(
                Record.activity_id == activity.id,
                Record.lat.isnot(None),
                Record.lon.isnot(None),
            )
            .order_by(Record.timestamp)
            .limit(1)
        )
        first_record = (await self._db.execute(record_query)).scalar_one_or_none()

        if not first_record or first_record.lat is None or first_record.lon is None:
            logger.info(f"Activity {activity.id} has no GPS data for weather fetch")
            activity.weather_status = WeatherStatus.NOT_APPLICABLE
            return False

        # Calculate duration in hours
        duration_hours = max(1, int((activity.elapsed_time_s or 3600) / 3600) + 1)

        # Fetch weather
        weather_result = await fetch_activity_weather(
            lat=first_record.lat,
            lon=first_record.lon,
            start_time=activity.started_at.replace(tzinfo=timezone.utc),
            duration_hours=duration_hours,
        )

        if not weather_result.success:
            logger.warning(f"Weather fetch failed for {activity.id}: {weather_result.error_message}")
            activity.weather_status = WeatherStatus.FAILED
            return False

        # Store hourly weather data
        for hourly in weather_result.hourly_data:
            weather_row = ActivityWeather(
                activity_id=activity.id,
                hour_offset=hourly.hour_offset,
                lat=weather_result.lat,
                lon=weather_result.lon,
                temperature_c=hourly.temperature_c,
                wind_speed_mps=hourly.wind_speed_mps,
                wind_direction_deg=hourly.wind_direction_deg,
                pressure_hpa=hourly.pressure_hpa,
                humidity_pct=hourly.humidity_pct,
                air_density=hourly.air_density,
            )
            self._db.add(weather_row)

        activity.weather_status = WeatherStatus.FETCHED
        await self._db.flush()

        logger.info(f"Stored {len(weather_result.hourly_data)} weather snapshots for activity {activity.id}")
        return True

    async def _run_aero_estimation(self, activity: Activity) -> bool:
        """Run CdA/Crr estimation using stored weather data."""
        # Load records for this activity
        records_query = (
            select(Record)
            .where(Record.activity_id == activity.id)
            .order_by(Record.timestamp)
        )
        records = (await self._db.execute(records_query)).scalars().all()

        if len(records) < 100:
            logger.info(f"Activity {activity.id} has insufficient records for aero estimation")
            return False

        # Build ActivityRecord list
        start_ts = records[0].timestamp
        activity_records = [
            ActivityRecord(
                timestamp_s=(r.timestamp - start_ts).total_seconds(),
                lat=r.lat,
                lon=r.lon,
                power_w=r.power_w,
                speed_mps=r.speed_mps,
                altitude_m=r.altitude_m,
                temperature_c=r.temperature_c,
                grade_pct=None,
            )
            for r in records
        ]

        # Check requirements
        can_estimate, reasons = check_estimation_requirements(
            activity_records,
            activity.power_source,
        )
        if not can_estimate:
            logger.info(f"Activity {activity.id} doesn't meet estimation requirements: {reasons}")
            return False

        # Load weather snapshots
        weather_query = select(ActivityWeather).where(ActivityWeather.activity_id == activity.id)
        weather_rows = (await self._db.execute(weather_query)).scalars().all()

        weather_snapshots = [
            WeatherSnapshot(
                hour_offset=w.hour_offset,
                wind_speed_mps=w.wind_speed_mps,
                wind_direction_deg=w.wind_direction_deg,
                pressure_hpa=w.pressure_hpa,
                humidity_pct=w.humidity_pct,
                temperature_c=w.temperature_c,
            )
            for w in weather_rows
        ]

        # Get user weight
        user = await self._db.get(User, activity.user_id)
        if not user or not user.weight_kg:
            logger.info(f"User {activity.user_id} has no weight set for aero estimation")
            return False

        # Get bike weight
        bike_weight = 9.0  # Default
        if activity.bike_id:
            bike = await self._db.get(Bike, activity.bike_id)
            if bike and bike.weight_kg:
                bike_weight = float(bike.weight_kg)

        total_mass = float(user.weight_kg) + bike_weight

        # Prepare data points with wind correction
        data_points, warnings = prepare_data_points(activity_records, weather_snapshots)

        if len(data_points) < 10:
            logger.info(f"Activity {activity.id} has insufficient valid data points: {len(data_points)}")
            return False

        # Run estimation
        estimation = estimate_cda_crr(data_points, total_mass)

        # Store results
        activity.estimated_cda = estimation.cda
        activity.estimated_crr = estimation.crr
        activity.aero_confidence = estimation.confidence

        logger.info(
            f"Aero estimation for {activity.id}: CdA={estimation.cda:.4f}, "
            f"Crr={estimation.crr:.5f}, confidence={estimation.confidence:.2f}"
        )

        # Update bike aggregates if confidence is sufficient
        if activity.bike_id and estimation.confidence > 0.3:
            await self._update_bike_aggregates(activity.bike_id)

        await self._db.flush()
        return True

    async def _update_bike_aggregates(self, bike_id: UUID) -> None:
        """Update bike's aggregate CdA/Crr from all valid activities."""
        from sqlalchemy import func

        # Calculate confidence-weighted averages
        result = await self._db.execute(
            select(
                func.sum(Activity.estimated_cda * Activity.aero_confidence).label("weighted_cda"),
                func.sum(Activity.estimated_crr * Activity.aero_confidence).label("weighted_crr"),
                func.sum(Activity.aero_confidence).label("total_weight"),
                func.count().label("count"),
            ).where(
                Activity.bike_id == bike_id,
                Activity.estimated_cda.isnot(None),
                Activity.aero_confidence > 0.3,
            )
        )
        row = result.one()

        if row.count == 0 or row.total_weight == 0:
            return

        avg_cda = row.weighted_cda / row.total_weight
        avg_crr = row.weighted_crr / row.total_weight

        # Calculate stddev
        stddev_result = await self._db.execute(
            select(
                func.stddev(Activity.estimated_cda).label("cda_stddev"),
                func.stddev(Activity.estimated_crr).label("crr_stddev"),
            ).where(
                Activity.bike_id == bike_id,
                Activity.estimated_cda.isnot(None),
                Activity.aero_confidence > 0.3,
            )
        )
        stddev_row = stddev_result.one()

        # Update bike
        bike = await self._db.get(Bike, bike_id)
        if bike:
            bike.estimated_cda_avg = avg_cda
            bike.estimated_crr_avg = avg_crr
            bike.estimated_cda_stddev = stddev_row.cda_stddev
            bike.estimated_crr_stddev = stddev_row.crr_stddev
            bike.aero_sample_count = row.count
