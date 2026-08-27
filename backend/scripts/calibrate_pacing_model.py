#!/usr/bin/env python3
"""
Calibration pipeline for pacing model validation.

Validates and calibrates the pacing model against real ride data from all
activities with power data. Runs entirely in-memory - no database writes.

Validates two key predictions:
1. NP/VI prediction (how well we predict normalized power from terrain)
2. Speed prediction (how well we predict segment speeds from power/terrain)

Usage:
    python scripts/calibrate_pacing_model.py [--output results.csv] [--user-id N]
"""

import argparse
import asyncio
import csv
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, stdev

import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select

from trainingdash.domain.course_segmentation import (
    CourseSegment,
    calculate_course_punchiness,
    segment_course,
)
from trainingdash.domain.elevation import smooth_elevation
from trainingdash.domain.fine_grained_pacing import (
    FineGrainedPlan,
    generate_fine_grained_plan,
)
from trainingdash.domain.grade import calculate_grade
from trainingdash.domain.physics import EnvironmentParams, RiderParams
from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Activity, Bike, PacingCoefficients, Record, User

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


from enum import StrEnum


# Default pacing coefficients (global defaults)
DEFAULT_GRADE_POWER_INTERCEPT = 1.10
DEFAULT_GRADE_POWER_SLOPE = 0.035
DEFAULT_MAX_DESCENT_SPEED_MPS = 18.0


class CoefficientsSource(StrEnum):
    """Source of pacing coefficients used for validation."""

    PERSONALIZED_BIKE = "personalized_bike"
    PERSONALIZED_USER = "personalized_user"
    GLOBAL_DEFAULTS = "global_defaults"


@dataclass
class ResolvedPacingCoefficients:
    """Pacing coefficients resolved for a specific user/bike.

    Bundles the grade-power relationship and descent speed parameters
    with their source for traceability.
    """

    grade_power_intercept: float
    grade_power_slope: float
    max_descent_speed_mps: float
    source: CoefficientsSource


@dataclass
class ValidationContext:
    """Context for validating an activity's pacing predictions.

    Groups rider/bike parameters and pacing coefficients to reduce
    parameter count in validate_activity().
    """

    rider_weight_kg: float
    bike_weight_kg: float
    cda: float
    crr: float
    coefficients: ResolvedPacingCoefficients


@dataclass
class ActivityResult:
    """Result of validating one activity.
    
    Attributes:
        activity_id: UUID of the activity.
        activity_title: Display name of the activity.
        activity_date: ISO date string of when activity occurred.
        course_type: Classification based on elevation (flat/rolling/hilly/mountainous).
        total_distance_km: Total distance in kilometers.
        elevation_gain_m: Total elevation gain in meters.
        elapsed_time_min: Total elapsed time in minutes.
        actual_avg_power: Measured average power in watts.
        actual_np: Measured Normalized Power in watts.
        actual_vi: Measured Variability Index (NP/avg).
        actual_avg_speed_kmh: Measured average speed in km/h.
        actual_time_s: Total elapsed time in seconds.
        actual_pedaling_time_s: Time spent pedaling (cadence > 0) in seconds.
        actual_pedaling_speed_kmh: Average speed while pedaling in km/h.
        pedaling_pct: Percentage of time spent actively pedaling.
        pred_vi: Predicted Variability Index from course punchiness.
        pred_np: Predicted Normalized Power using VI correction.
        pred_avg_speed_kmh: Predicted average speed from physics model.
        pred_time_s: Predicted total time from physics model.
        np_error_pct: NP prediction error as percentage.
        vi_error_pct: VI prediction error as percentage.
        speed_error_pct: Speed prediction error vs total ride.
        time_error_pct: Time prediction error vs total ride.
        pedaling_speed_error_pct: Speed error vs pedaling-only speed.
        pedaling_time_error_pct: Time error vs pedaling-only time.
        grade_stddev: Standard deviation of grades (punchiness metric).
        steep_climb_fraction: Fraction of distance on steep climbs.
        rider_mass_kg: Total mass (rider + bike + gear) used.
        cda: Aerodynamic drag area used.
        crr: Rolling resistance coefficient used.
        grade_power_intercept: Grade-power formula intercept used.
        grade_power_slope: Grade-power formula slope used.
        max_descent_speed_mps: Max descent speed cap used.
        coefficients_source: Where pacing coefficients came from.
        status: Validation status (success/skipped/error).
        notes: Additional notes or error messages.
    """

    activity_id: str
    activity_title: str
    activity_date: str
    course_type: str
    total_distance_km: float
    elevation_gain_m: float
    elapsed_time_min: float
    # Actual values (total ride including stops)
    actual_avg_power: float
    actual_np: float
    actual_vi: float
    actual_avg_speed_kmh: float
    actual_time_s: float
    # Actual values (pedaling-only: cadence > 0)
    actual_pedaling_time_s: float
    actual_pedaling_speed_kmh: float
    pedaling_pct: float
    # Predicted values
    pred_vi: float
    pred_np: float
    pred_avg_speed_kmh: float
    pred_time_s: float
    # Errors (vs total ride)
    np_error_pct: float
    vi_error_pct: float
    speed_error_pct: float
    time_error_pct: float
    # Errors (vs pedaling-only)
    pedaling_speed_error_pct: float
    pedaling_time_error_pct: float
    # Punchiness details
    grade_stddev: float
    steep_climb_fraction: float
    # Rider params used
    rider_mass_kg: float
    cda: float
    crr: float
    # Pacing coefficients used
    grade_power_intercept: float
    grade_power_slope: float
    max_descent_speed_mps: float
    coefficients_source: CoefficientsSource | str
    # Status
    status: str
    notes: str

    @classmethod
    def skipped(
        cls,
        activity: "Activity",
        pedaling_metrics: "PedalingMetrics | None",
        notes: str,
    ) -> "ActivityResult":
        """Create a skipped result for an activity that couldn't be validated.
        
        Args:
            activity: The activity that was skipped.
            pedaling_metrics: Pedaling metrics if available, None otherwise.
            notes: Reason for skipping.
            
        Returns:
            ActivityResult with status="skipped" and zeroed predictions.
        """
        return cls(
            activity_id=str(activity.id),
            activity_title=activity.title or "Untitled",
            activity_date=activity.started_at.strftime("%Y-%m-%d") if activity.started_at else "",
            course_type="",
            total_distance_km=activity.total_distance_m / 1000 if activity.total_distance_m else 0,
            elevation_gain_m=float(activity.elevation_gain_m) if activity.elevation_gain_m else 0,
            elapsed_time_min=activity.elapsed_time_s / 60 if activity.elapsed_time_s else 0,
            actual_avg_power=float(activity.avg_power_w) if activity.avg_power_w else 0,
            actual_np=float(activity.np_power_w) if activity.np_power_w else 0,
            actual_vi=(
                float(activity.np_power_w) / float(activity.avg_power_w)
                if activity.avg_power_w and activity.np_power_w
                else 0
            ),
            actual_avg_speed_kmh=(
                activity.total_distance_m / activity.elapsed_time_s * 3.6
                if activity.elapsed_time_s and activity.total_distance_m
                else 0
            ),
            actual_time_s=float(activity.elapsed_time_s) if activity.elapsed_time_s else 0,
            actual_pedaling_time_s=pedaling_metrics.pedaling_time_s if pedaling_metrics else 0,
            actual_pedaling_speed_kmh=0,
            pedaling_pct=pedaling_metrics.pedaling_pct if pedaling_metrics else 0,
            pred_vi=0,
            pred_np=0,
            pred_avg_speed_kmh=0,
            pred_time_s=0,
            np_error_pct=0,
            vi_error_pct=0,
            speed_error_pct=0,
            time_error_pct=0,
            pedaling_speed_error_pct=0,
            pedaling_time_error_pct=0,
            grade_stddev=0,
            steep_climb_fraction=0,
            rider_mass_kg=0,
            cda=0,
            crr=0,
            grade_power_intercept=0,
            grade_power_slope=0,
            max_descent_speed_mps=0,
            coefficients_source="",
            status="skipped",
            notes=notes,
        )


async def get_activities_with_power(user_id: int | None = None) -> list[Activity]:
    """Get all activities with measured power data."""
    async with async_session() as db:
        query = (
            select(Activity)
            .where(
                Activity.avg_power_w.isnot(None),
                Activity.np_power_w.isnot(None),
                Activity.total_distance_m > 1000,  # At least 1km
                Activity.elapsed_time_s > 600,  # At least 10 minutes
                Activity.power_source == "measured",  # Only actual power meters
            )
            .order_by(Activity.started_at.desc())
        )

        if user_id is not None:
            query = query.where(Activity.user_id == user_id)

        result = await db.execute(query)
        return list(result.scalars().all())


async def get_records_for_activity(activity_id: str) -> list[Record]:
    """Get all records for an activity."""
    async with async_session() as db:
        result = await db.execute(select(Record).where(Record.activity_id == activity_id).order_by(Record.distance_m))
        return list(result.scalars().all())


async def get_user_weight(user_id: int) -> float:
    """Get user weight from profile."""
    async with async_session() as db:
        result = await db.execute(select(User.weight_kg).where(User.id == user_id))
        weight = result.scalar_one_or_none()
        return float(weight) if weight else 75.0  # Default 75kg


async def get_bike_for_activity(activity: Activity) -> tuple[float, float, float]:
    """
    Get bike parameters (weight, CdA, Crr) for an activity.

    Returns:
        Tuple of (bike_weight_kg, cda, crr) with defaults if not available.
    """
    default_bike_weight = 8.0
    default_cda = 0.32
    default_crr = 0.004

    if activity.bike_id is None:
        return default_bike_weight, default_cda, default_crr

    async with async_session() as db:
        result = await db.execute(select(Bike).where(Bike.id == activity.bike_id))
        bike = result.scalar_one_or_none()

        if bike is None:
            return default_bike_weight, default_cda, default_crr

        bike_weight = float(bike.weight_kg) if bike.weight_kg else default_bike_weight

        # Prefer estimated CdA/Crr from calibration if available
        if bike.estimated_cda_avg is not None:
            cda = float(bike.estimated_cda_avg)
        elif bike.cda is not None:
            cda = float(bike.cda)
        else:
            cda = default_cda

        if bike.estimated_crr_avg is not None:
            crr = float(bike.estimated_crr_avg)
        elif bike.crr is not None:
            crr = float(bike.crr)
        else:
            crr = default_crr

        return bike_weight, cda, crr


async def get_pacing_coefficients(
    user_id: int, bike_id: int | None
) -> ResolvedPacingCoefficients:
    """
    Get personalized pacing coefficients for a user/bike.

    Fallback chain: bike-specific → user default → global defaults

    Returns:
        ResolvedPacingCoefficients with the coefficients and their source.
    """
    async with async_session() as db:
        # Try bike-specific coefficients first
        if bike_id is not None:
            result = await db.execute(
                select(PacingCoefficients).where(
                    PacingCoefficients.user_id == user_id,
                    PacingCoefficients.bike_id == bike_id,
                )
            )
            coeff = result.scalar_one_or_none()
            if coeff is not None:
                return ResolvedPacingCoefficients(
                    grade_power_intercept=float(coeff.grade_power_intercept),
                    grade_power_slope=float(coeff.grade_power_slope),
                    max_descent_speed_mps=float(coeff.max_descent_speed_mps),
                    source=CoefficientsSource.PERSONALIZED_BIKE,
                )

        # Try user default (bike_id = NULL)
        result = await db.execute(
            select(PacingCoefficients).where(
                PacingCoefficients.user_id == user_id,
                PacingCoefficients.bike_id.is_(None),
            )
        )
        coeff = result.scalar_one_or_none()
        if coeff is not None:
            return ResolvedPacingCoefficients(
                grade_power_intercept=float(coeff.grade_power_intercept),
                grade_power_slope=float(coeff.grade_power_slope),
                max_descent_speed_mps=float(coeff.max_descent_speed_mps),
                source=CoefficientsSource.PERSONALIZED_USER,
            )

        # Fall back to global defaults
        return ResolvedPacingCoefficients(
            grade_power_intercept=DEFAULT_GRADE_POWER_INTERCEPT,
            grade_power_slope=DEFAULT_GRADE_POWER_SLOPE,
            max_descent_speed_mps=DEFAULT_MAX_DESCENT_SPEED_MPS,
            source=CoefficientsSource.GLOBAL_DEFAULTS,
        )


@dataclass
class PedalingMetrics:
    """Metrics tracking pedaling vs coasting/stopped time.
    
    Used to separate physics-relevant riding time from total elapsed time,
    enabling more accurate model validation by comparing predictions against
    actual pedaling speed rather than overall average speed.
    """

    pedaling_time_s: float  # Time with cadence > 0
    total_time_s: float  # Total elapsed time
    pedaling_distance_m: float  # Distance covered while pedaling
    pedaling_pct: float  # % of time spent pedaling


def calculate_pedaling_metrics(records: list[Record]) -> PedalingMetrics:
    """
    Calculate pedaling-only metrics from activity records.

    Uses cadence_rpm > 0 as signal for "actively pedaling" vs coasting/stopped.
    """
    if len(records) < 2:
        return PedalingMetrics(0, 0, 0, 0)

    pedaling_time_s = 0.0
    total_time_s = 0.0
    pedaling_distance_m = 0.0

    for i in range(1, len(records)):
        prev_rec = records[i - 1]
        curr_rec = records[i]

        # Calculate time delta
        time_delta = (curr_rec.timestamp - prev_rec.timestamp).total_seconds()
        if time_delta <= 0 or time_delta > 60:  # Skip bad intervals (>60s gap)
            continue

        total_time_s += time_delta

        # Calculate distance delta
        dist_delta = curr_rec.distance_m - prev_rec.distance_m
        if dist_delta < 0:
            dist_delta = 0

        # Check if pedaling (cadence > 0 at either endpoint means actively pedaling)
        prev_cadence = prev_rec.cadence_rpm or 0
        curr_cadence = curr_rec.cadence_rpm or 0

        if prev_cadence > 0 or curr_cadence > 0:
            pedaling_time_s += time_delta
            pedaling_distance_m += dist_delta

    pedaling_pct = (pedaling_time_s / total_time_s * 100) if total_time_s > 0 else 0

    return PedalingMetrics(
        pedaling_time_s=pedaling_time_s,
        total_time_s=total_time_s,
        pedaling_distance_m=pedaling_distance_m,
        pedaling_pct=pedaling_pct,
    )


def create_segments_from_records(records: list[Record]) -> tuple[list[CourseSegment], list[dict], PedalingMetrics, str]:
    """
    Create course segments and elevation profile from activity records.

    Returns:
        Tuple of (segments, elevation_profile, pedaling_metrics, notes).
    """
    notes = []

    # Calculate pedaling metrics from all records (before filtering)
    pedaling_metrics = calculate_pedaling_metrics(records)

    # Filter to records with GPS and elevation
    valid_records = [r for r in records if r.lat is not None and r.lon is not None and r.altitude_m is not None]

    if len(valid_records) < 20:
        return [], [], pedaling_metrics, "Insufficient GPS/elevation data"

    # Extract arrays
    distances = np.array([r.distance_m for r in valid_records])
    elevations = np.array([r.altitude_m for r in valid_records])
    lats = [r.lat for r in valid_records]
    lons = [r.lon for r in valid_records]

    # Check for monotonic distance (sometimes records are duplicated)
    if not np.all(np.diff(distances) >= 0):
        # Fix by removing non-monotonic points
        mask = np.concatenate([[True], np.diff(distances) > 0])
        distances = distances[mask]
        elevations = elevations[mask]
        lats = [lat for lat, m in zip(lats, mask) if m]
        lons = [lon for lon, m in zip(lons, mask) if m]
        notes.append("Fixed non-monotonic distances")

    if len(distances) < 20:
        return [], [], pedaling_metrics, "Insufficient data after cleanup"

    # Smooth elevation and calculate grades
    smoothed_elevations = smooth_elevation(elevations)
    grades = calculate_grade(distances, smoothed_elevations)

    # Create elevation profile for fine-grained pacing (with lat/lon for curvature)
    elevation_profile = []
    for i, (dist, elev) in enumerate(zip(distances, smoothed_elevations)):
        grade = grades[i] if i < len(grades) else 0.0
        elevation_profile.append({
            "distance_m": float(dist),
            "elevation_m": float(elev),
            "grade_pct": float(grade),
            "lat": lats[i] if i < len(lats) else None,
            "lon": lons[i] if i < len(lons) else None,
        })

    # Segment the course
    segments = segment_course(distances, grades, smoothed_elevations)

    if not segments:
        return [], elevation_profile, pedaling_metrics, "Segmentation failed"

    return segments, elevation_profile, pedaling_metrics, "; ".join(notes) if notes else ""


def validate_activity(
    activity: Activity,
    segments: list[CourseSegment],
    elevation_profile: list[dict],
    pedaling_metrics: PedalingMetrics,
    context: ValidationContext,
) -> ActivityResult:
    """
    Validate pacing model prediction against actual activity data.

    Validates both:
    1. NP/VI prediction (using course punchiness)
    2. Speed/time prediction (using fine-grained pacing engine with personalized coefficients)

    Args:
        activity: The activity to validate.
        segments: Course segments derived from activity GPS data.
        elevation_profile: Elevation profile for fine-grained pacing.
        pedaling_metrics: Pedaling vs coasting metrics.
        context: Validation context with rider/bike params and pacing coefficients.

    Returns:
        ActivityResult with predictions and errors.
    """
    # Calculate punchiness and expected VI
    punchiness = calculate_course_punchiness(segments)

    # Actual values from activity (total ride including stops)
    actual_avg = float(activity.avg_power_w)
    actual_np = float(activity.np_power_w)
    actual_vi = actual_np / actual_avg if actual_avg > 0 else 1.0
    actual_time_s = float(activity.elapsed_time_s)
    actual_distance_m = float(activity.total_distance_m)
    actual_avg_speed_mps = actual_distance_m / actual_time_s if actual_time_s > 0 else 0
    actual_avg_speed_kmh = actual_avg_speed_mps * 3.6

    # Actual pedaling-only values (more meaningful for physics comparison)
    actual_pedaling_time_s = pedaling_metrics.pedaling_time_s
    actual_pedaling_speed_kmh = (
        (actual_distance_m / actual_pedaling_time_s * 3.6)
        if actual_pedaling_time_s > 0
        else actual_avg_speed_kmh
    )
    pedaling_pct = pedaling_metrics.pedaling_pct

    # Predicted NP using VI correction
    pred_vi = punchiness.expected_vi
    pred_np = actual_avg * pred_vi  # Use actual avg power to isolate VI prediction

    # =========================================================================
    # Speed prediction using fine-grained pacing engine
    # =========================================================================
    # Use actual average power as "target" to see how well we predict speed
    total_mass_kg = context.rider_weight_kg + context.bike_weight_kg + 3.0  # +3kg for gear
    rider_params = RiderParams(mass_kg=total_mass_kg, cda=context.cda, crr=context.crr)

    # Calculate target intensity from actual power and estimated FTP
    # Assume FTP ~ actual_np for tempo-ish efforts, or avg_power * 1.1 for easier
    estimated_ftp = max(actual_np, actual_avg * 1.1)
    target_intensity = actual_avg / estimated_ftp

    # Generate fine-grained prediction using personalized coefficients
    coeff = context.coefficients
    fine_plan = generate_fine_grained_plan(
        elevation_profile=elevation_profile,
        rider_ftp=estimated_ftp,
        target_intensity=target_intensity,
        rider_params=rider_params,
        env_params=EnvironmentParams(),  # Default sea level
        grade_power_intercept=coeff.grade_power_intercept,
        grade_power_slope=coeff.grade_power_slope,
        max_descent_speed_mps=coeff.max_descent_speed_mps,
        power_cap_ftp_pct=1.5,  # Allow higher for real-world variation
        target_spacing_m=25.0,
    )

    pred_time_s = fine_plan.total_time_s if fine_plan.points else 0
    pred_distance_m = fine_plan.total_distance_m if fine_plan.points else actual_distance_m
    pred_avg_speed_mps = pred_distance_m / pred_time_s if pred_time_s > 0 else 0
    pred_avg_speed_kmh = pred_avg_speed_mps * 3.6

    # Calculate errors (vs total ride)
    np_error_pct = abs(pred_np - actual_np) / actual_np * 100 if actual_np > 0 else 0
    vi_error_pct = abs(pred_vi - actual_vi) / actual_vi * 100 if actual_vi > 0 else 0
    speed_error_pct = abs(pred_avg_speed_kmh - actual_avg_speed_kmh) / actual_avg_speed_kmh * 100 if actual_avg_speed_kmh > 0 else 0
    time_error_pct = abs(pred_time_s - actual_time_s) / actual_time_s * 100 if actual_time_s > 0 else 0

    # Calculate errors vs pedaling-only (more meaningful for physics validation)
    pedaling_speed_error_pct = (
        abs(pred_avg_speed_kmh - actual_pedaling_speed_kmh) / actual_pedaling_speed_kmh * 100
        if actual_pedaling_speed_kmh > 0
        else speed_error_pct
    )
    pedaling_time_error_pct = (
        abs(pred_time_s - actual_pedaling_time_s) / actual_pedaling_time_s * 100
        if actual_pedaling_time_s > 0
        else time_error_pct
    )

    return ActivityResult(
        activity_id=str(activity.id),
        activity_title=activity.title or "Untitled",
        activity_date=activity.started_at.strftime("%Y-%m-%d"),
        course_type=punchiness.course_type,
        total_distance_km=activity.total_distance_m / 1000,
        elevation_gain_m=activity.elevation_gain_m,
        elapsed_time_min=activity.elapsed_time_s / 60,
        actual_avg_power=actual_avg,
        actual_np=actual_np,
        actual_vi=actual_vi,
        actual_avg_speed_kmh=actual_avg_speed_kmh,
        actual_time_s=actual_time_s,
        actual_pedaling_time_s=actual_pedaling_time_s,
        actual_pedaling_speed_kmh=actual_pedaling_speed_kmh,
        pedaling_pct=pedaling_pct,
        pred_vi=pred_vi,
        pred_np=pred_np,
        pred_avg_speed_kmh=pred_avg_speed_kmh,
        pred_time_s=pred_time_s,
        np_error_pct=np_error_pct,
        vi_error_pct=vi_error_pct,
        speed_error_pct=speed_error_pct,
        time_error_pct=time_error_pct,
        pedaling_speed_error_pct=pedaling_speed_error_pct,
        pedaling_time_error_pct=pedaling_time_error_pct,
        grade_stddev=punchiness.grade_stddev,
        steep_climb_fraction=punchiness.steep_climb_fraction,
        rider_mass_kg=total_mass_kg,
        cda=context.cda,
        crr=context.crr,
        grade_power_intercept=coeff.grade_power_intercept,
        grade_power_slope=coeff.grade_power_slope,
        max_descent_speed_mps=coeff.max_descent_speed_mps,
        coefficients_source=coeff.source,
        status="success",
        notes="",
    )


async def run_calibration(
    user_id: int | None = None,
    output_path: str = "calibration_results.csv",
) -> list[ActivityResult]:
    """Run calibration pipeline across all qualifying activities."""

    logger.info("Starting calibration pipeline...")

    # Get activities
    activities = await get_activities_with_power(user_id)
    logger.info(f"Found {len(activities)} activities with power data")

    results: list[ActivityResult] = []

    for i, activity in enumerate(activities):
        logger.info(f"Processing {i + 1}/{len(activities)}: {activity.title or activity.id}")

        try:
            # Get records
            records = await get_records_for_activity(str(activity.id))

            if not records:
                results.append(ActivityResult.skipped(activity, None, "No records found"))
                continue

            # Create segments and elevation profile
            segments, elevation_profile, pedaling_metrics, notes = create_segments_from_records(records)

            if not segments:
                results.append(ActivityResult.skipped(activity, pedaling_metrics, notes))
                continue

            # Get rider and bike parameters
            rider_weight = await get_user_weight(activity.user_id)
            bike_weight, cda, crr = await get_bike_for_activity(activity)

            # Get personalized pacing coefficients
            pacing_coefficients = await get_pacing_coefficients(
                activity.user_id, activity.bike_id
            )

            # Build validation context
            context = ValidationContext(
                rider_weight_kg=rider_weight,
                bike_weight_kg=bike_weight,
                cda=cda,
                crr=crr,
                coefficients=pacing_coefficients,
            )

            # Validate
            result = validate_activity(
                activity,
                segments,
                elevation_profile,
                pedaling_metrics,
                context,
            )
            if notes:
                result.notes = notes
            results.append(result)

        except Exception as e:
            logger.error(f"Error processing {activity.id}: {e}")
            results.append(ActivityResult.skipped(activity, None, f"Error: {e}"))

    # Write CSV
    write_csv(results, output_path)

    # Print summary
    print_summary(results)

    return results


def write_csv(results: list[ActivityResult], output_path: str) -> None:
    """Write results to CSV file."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "activity_id",
                "activity_title",
                "activity_date",
                "course_type",
                "distance_km",
                "elevation_gain_m",
                "elapsed_time_min",
                "actual_avg_power",
                "actual_np",
                "actual_vi",
                "actual_avg_speed_kmh",
                "actual_time_s",
                "actual_pedaling_time_s",
                "actual_pedaling_speed_kmh",
                "pedaling_pct",
                "pred_vi",
                "pred_np",
                "pred_avg_speed_kmh",
                "pred_time_s",
                "np_error_pct",
                "vi_error_pct",
                "speed_error_pct",
                "time_error_pct",
                "pedaling_speed_error_pct",
                "pedaling_time_error_pct",
                "grade_stddev",
                "steep_climb_fraction",
                "rider_mass_kg",
                "cda",
                "crr",
                "grade_power_intercept",
                "grade_power_slope",
                "max_descent_speed_mps",
                "coefficients_source",
                "status",
                "notes",
            ]
        )

        for r in results:
            writer.writerow(
                [
                    r.activity_id,
                    r.activity_title,
                    r.activity_date,
                    r.course_type,
                    f"{r.total_distance_km:.2f}",
                    f"{r.elevation_gain_m:.0f}",
                    f"{r.elapsed_time_min:.1f}",
                    f"{r.actual_avg_power:.0f}",
                    f"{r.actual_np:.0f}",
                    f"{r.actual_vi:.3f}",
                    f"{r.actual_avg_speed_kmh:.1f}",
                    f"{r.actual_time_s:.0f}",
                    f"{r.actual_pedaling_time_s:.0f}",
                    f"{r.actual_pedaling_speed_kmh:.1f}",
                    f"{r.pedaling_pct:.1f}",
                    f"{r.pred_vi:.3f}",
                    f"{r.pred_np:.0f}",
                    f"{r.pred_avg_speed_kmh:.1f}",
                    f"{r.pred_time_s:.0f}",
                    f"{r.np_error_pct:.1f}",
                    f"{r.vi_error_pct:.1f}",
                    f"{r.speed_error_pct:.1f}",
                    f"{r.time_error_pct:.1f}",
                    f"{r.pedaling_speed_error_pct:.1f}",
                    f"{r.pedaling_time_error_pct:.1f}",
                    f"{r.grade_stddev:.2f}",
                    f"{r.steep_climb_fraction:.3f}",
                    f"{r.rider_mass_kg:.1f}",
                    f"{r.cda:.4f}",
                    f"{r.crr:.4f}",
                    f"{r.grade_power_intercept:.3f}",
                    f"{r.grade_power_slope:.4f}",
                    f"{r.max_descent_speed_mps:.1f}",
                    r.coefficients_source,
                    r.status,
                    r.notes,
                ]
            )

    logger.info(f"Results written to {output_path}")


def print_summary(results: list[ActivityResult]) -> None:
    """Print summary statistics."""
    successful = [r for r in results if r.status == "success"]
    skipped = [r for r in results if r.status == "skipped"]
    errors = [r for r in results if r.status == "error"]

    print("\n" + "=" * 70)
    print("CALIBRATION SUMMARY")
    print("=" * 70)
    print(f"\nTotal activities: {len(results)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  Errors: {len(errors)}")

    if not successful:
        print("\nNo successful validations to analyze.")
        return

    # Pedaling metrics overview
    pedaling_pcts = [r.pedaling_pct for r in successful if r.pedaling_pct > 0]
    if pedaling_pcts:
        print("\n" + "-" * 70)
        print("PEDALING VS COASTING/STOPPED")
        print("-" * 70)
        print(f"  Avg time spent pedaling: {mean(pedaling_pcts):.1f}%")
        print(f"  Range: {min(pedaling_pcts):.1f}% - {max(pedaling_pcts):.1f}%")
        print("  (Remaining time is coasting, stopped at lights, etc.)")

    # Coefficients source breakdown
    coeff_sources = {}
    for r in successful:
        coeff_sources[r.coefficients_source] = coeff_sources.get(r.coefficients_source, 0) + 1

    print("\n" + "-" * 70)
    print("PACING COEFFICIENTS USED")
    print("-" * 70)
    for source, count in sorted(coeff_sources.items()):
        pct = count / len(successful) * 100
        print(f"  {source}: {count} activities ({pct:.0f}%)")

    # Show the actual coefficients used (from first personalized result)
    personalized = [r for r in successful if r.coefficients_source != "global_defaults"]
    if personalized:
        r = personalized[0]
        print(f"\nPersonalized coefficients:")
        print(f"  grade_power_intercept: {r.grade_power_intercept:.3f} (global default: {DEFAULT_GRADE_POWER_INTERCEPT:.3f})")
        print(f"  grade_power_slope: {r.grade_power_slope:.4f} (global default: {DEFAULT_GRADE_POWER_SLOPE:.4f})")
        print(f"  max_descent_speed_mps: {r.max_descent_speed_mps:.1f} (global default: {DEFAULT_MAX_DESCENT_SPEED_MPS:.1f})")

    # Overall stats
    np_errors = [r.np_error_pct for r in successful]
    vi_errors = [r.vi_error_pct for r in successful]
    speed_errors = [r.speed_error_pct for r in successful]
    time_errors = [r.time_error_pct for r in successful]
    pedaling_speed_errors = [r.pedaling_speed_error_pct for r in successful if r.pedaling_pct > 0]
    pedaling_time_errors = [r.pedaling_time_error_pct for r in successful if r.pedaling_pct > 0]

    print("\n" + "-" * 70)
    print("NP/VI PREDICTION ACCURACY")
    print("-" * 70)

    print("\nNP Error:")
    print(f"  Mean: {mean(np_errors):.1f}%")
    print(f"  Median: {median(np_errors):.1f}%")
    print(f"  Std Dev: {stdev(np_errors):.1f}%" if len(np_errors) > 1 else "  Std Dev: N/A")
    print(f"  Min: {min(np_errors):.1f}%")
    print(f"  Max: {max(np_errors):.1f}%")

    print("\nVI Error:")
    print(f"  Mean: {mean(vi_errors):.1f}%")
    print(f"  Median: {median(vi_errors):.1f}%")
    print(f"  Std Dev: {stdev(vi_errors):.1f}%" if len(vi_errors) > 1 else "  Std Dev: N/A")

    print("\n" + "-" * 70)
    print("SPEED/TIME PREDICTION ACCURACY (Fine-Grained Pacing)")
    print("-" * 70)

    print("\n** VS TOTAL RIDE (includes stops/coasting) **")
    print("\nSpeed Error:")
    print(f"  Mean: {mean(speed_errors):.1f}%")
    print(f"  Median: {median(speed_errors):.1f}%")
    print(f"  Std Dev: {stdev(speed_errors):.1f}%" if len(speed_errors) > 1 else "  Std Dev: N/A")
    print(f"  Min: {min(speed_errors):.1f}%")
    print(f"  Max: {max(speed_errors):.1f}%")

    print("\nTime Error:")
    print(f"  Mean: {mean(time_errors):.1f}%")
    print(f"  Median: {median(time_errors):.1f}%")
    print(f"  Std Dev: {stdev(time_errors):.1f}%" if len(time_errors) > 1 else "  Std Dev: N/A")

    # Pedaling-only comparison (the key metric for physics validation)
    if pedaling_speed_errors:
        print("\n** VS PEDALING-ONLY (cadence > 0) - PHYSICS MODEL ACCURACY **")
        print("\nPedaling Speed Error:")
        print(f"  Mean: {mean(pedaling_speed_errors):.1f}%")
        print(f"  Median: {median(pedaling_speed_errors):.1f}%")
        print(f"  Std Dev: {stdev(pedaling_speed_errors):.1f}%" if len(pedaling_speed_errors) > 1 else "  Std Dev: N/A")

        print("\nPedaling Time Error:")
        print(f"  Mean: {mean(pedaling_time_errors):.1f}%")
        print(f"  Median: {median(pedaling_time_errors):.1f}%")

    # Actual vs predicted comparison
    actual_speeds = [r.actual_avg_speed_kmh for r in successful]
    pred_speeds = [r.pred_avg_speed_kmh for r in successful]
    pedaling_speeds = [r.actual_pedaling_speed_kmh for r in successful if r.pedaling_pct > 0]

    print("\nSpeed Comparison:")
    print(f"  Actual total avg: {mean(actual_speeds):.1f} km/h (includes stops)")
    if pedaling_speeds:
        print(f"  Actual pedaling avg: {mean(pedaling_speeds):.1f} km/h (cadence > 0 only)")
    print(f"  Predicted avg: {mean(pred_speeds):.1f} km/h")

    speed_bias = mean([r.pred_avg_speed_kmh - r.actual_avg_speed_kmh for r in successful])
    print(f"\n  Bias vs total: {speed_bias:+.1f} km/h (positive = over-predicting)")

    if pedaling_speeds:
        pedaling_bias = mean([r.pred_avg_speed_kmh - r.actual_pedaling_speed_kmh for r in successful if r.pedaling_pct > 0])
        print(f"  Bias vs pedaling: {pedaling_bias:+.1f} km/h (true physics error)")

    # By course type
    print("\n" + "-" * 70)
    print("BY COURSE TYPE")
    print("-" * 70)

    course_types = {r.course_type for r in successful}
    for ct in sorted(course_types):
        ct_results = [r for r in successful if r.course_type == ct]
        ct_np_errors = [r.np_error_pct for r in ct_results]
        ct_speed_errors = [r.speed_error_pct for r in ct_results]
        ct_pedaling_speed_errors = [r.pedaling_speed_error_pct for r in ct_results if r.pedaling_pct > 0]
        ct_pedaling_pcts = [r.pedaling_pct for r in ct_results if r.pedaling_pct > 0]

        print(f"\n  {ct.upper()} (n={len(ct_results)}):")
        print(f"    NP Error: mean={mean(ct_np_errors):.1f}%, median={median(ct_np_errors):.1f}%")
        print(f"    Speed Error (total): mean={mean(ct_speed_errors):.1f}%")
        if ct_pedaling_speed_errors:
            print(f"    Speed Error (pedaling): mean={mean(ct_pedaling_speed_errors):.1f}%")
            print(f"    Avg pedaling %: {mean(ct_pedaling_pcts):.1f}%")

        # Speed bias for this terrain
        ct_speed_bias = mean([r.pred_avg_speed_kmh - r.actual_avg_speed_kmh for r in ct_results])
        print(f"    Speed Bias (total): {ct_speed_bias:+.1f} km/h")

    # Identify speed outliers (>20% error vs pedaling)
    pedaling_outliers = [r for r in successful if r.pedaling_speed_error_pct > 20 and r.pedaling_pct > 0]
    if pedaling_outliers:
        print(f"\n" + "-" * 70)
        print(f"PEDALING SPEED OUTLIERS (error >20%): {len(pedaling_outliers)}")
        print("-" * 70)
        for r in sorted(pedaling_outliers, key=lambda x: -x.pedaling_speed_error_pct)[:5]:
            print(
                f"  {r.activity_title} ({r.activity_date}): "
                f"{r.pedaling_speed_error_pct:.1f}% error, "
                f"pedaling={r.actual_pedaling_speed_kmh:.1f} vs pred={r.pred_avg_speed_kmh:.1f} km/h "
                f"({r.pedaling_pct:.0f}% pedaling)"
            )

    # Identify NP outliers (>20% error)
    np_outliers = [r for r in successful if r.np_error_pct > 20]
    if np_outliers:
        print(f"\nNP OUTLIERS (error >20%): {len(np_outliers)}")
        for r in sorted(np_outliers, key=lambda x: -x.np_error_pct)[:5]:
            print(
                f"  {r.activity_title} ({r.activity_date}): {r.np_error_pct:.1f}% error, VI actual={r.actual_vi:.3f} vs pred={r.pred_vi:.3f}"
            )

    # Coefficient recommendations
    print("\n" + "-" * 70)
    print("RECOMMENDATIONS")
    print("-" * 70)

    # Calculate systematic bias
    vi_biases = [r.pred_vi - r.actual_vi for r in successful]
    mean_vi_bias = mean(vi_biases)
    print(f"\nVI Prediction Bias: {mean_vi_bias:+.3f} (positive = over-predicting)")

    if abs(mean_vi_bias) > 0.02:
        print(f"  Recommendation: Adjust base VI by {-mean_vi_bias:+.3f}")
    else:
        print("  VI bias is within acceptable range.")

    # Speed bias analysis - focus on pedaling-only
    if pedaling_speeds:
        pedaling_bias = mean([r.pred_avg_speed_kmh - r.actual_pedaling_speed_kmh for r in successful if r.pedaling_pct > 0])
        if abs(pedaling_bias) > 2.0:
            if pedaling_bias > 0:
                print(f"\nPedaling speed is over-predicted by {pedaling_bias:.1f} km/h on average.")
                print("  Possible causes:")
                print("    - CdA too low (check wind tunnel / aero estimates)")
                print("    - Crr too low (check tire/road conditions)")
                print("    - Curves/hairpins not accounted for (curvature coefficient not applied)")
            else:
                print(f"\nPedaling speed is under-predicted by {abs(pedaling_bias):.1f} km/h on average.")
                print("  Possible causes:")
                print("    - CdA too high")
                print("    - Crr too high")
                print("    - Rider weight overestimated")
        else:
            print(f"\nPedaling speed prediction bias is excellent ({pedaling_bias:+.1f} km/h)!")
            print("  The physics model is accurate for active pedaling time.")

        coasting_factor = mean([r.actual_avg_speed_kmh / r.actual_pedaling_speed_kmh for r in successful if r.pedaling_pct > 0 and r.actual_pedaling_speed_kmh > 0])
        print(f"\n  Coasting/stop factor: {coasting_factor:.2f}x")
        print(f"  (Multiply predicted time by {1/coasting_factor:.2f} to estimate total ride time)")
    else:
        # Fall back to total ride analysis
        if abs(speed_bias) > 2.0:
            if speed_bias > 0:
                print(f"\nSpeed is over-predicted by {speed_bias:.1f} km/h on average.")
                print("  Possible causes:")
                print("    - CdA too low (check wind tunnel / aero estimates)")
                print("    - Crr too low (check tire/road conditions)")
                print("    - Not accounting for stops/coasting")
            else:
                print(f"\nSpeed is under-predicted by {abs(speed_bias):.1f} km/h on average.")
                print("  Possible causes:")
                print("    - CdA too high")
                print("    - Crr too high")
                print("    - Rider weight overestimated")
        else:
            print(f"\nSpeed prediction bias is within acceptable range ({speed_bias:+.1f} km/h).")


def main():
    parser = argparse.ArgumentParser(description="Calibrate pacing model against real ride data")
    parser.add_argument("--output", "-o", default="calibration_results.csv", help="Output CSV path")
    parser.add_argument("--user-id", "-u", type=int, help="Filter to specific user ID")
    args = parser.parse_args()

    asyncio.run(run_calibration(user_id=args.user_id, output_path=args.output))


if __name__ == "__main__":
    main()
