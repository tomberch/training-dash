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
from trainingdash.repositories.postgres.models import Activity, Bike, Record, User

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ActivityResult:
    """Result of validating one activity."""

    activity_id: str
    activity_title: str
    activity_date: str
    course_type: str
    total_distance_km: float
    elevation_gain_m: float
    elapsed_time_min: float
    # Actual values
    actual_avg_power: float
    actual_np: float
    actual_vi: float
    actual_avg_speed_kmh: float
    actual_time_s: float
    # Predicted values
    pred_vi: float
    pred_np: float
    pred_avg_speed_kmh: float
    pred_time_s: float
    # Errors
    np_error_pct: float
    vi_error_pct: float
    speed_error_pct: float
    time_error_pct: float
    # Punchiness details
    grade_stddev: float
    steep_climb_fraction: float
    # Rider params used
    rider_mass_kg: float
    cda: float
    crr: float
    # Status
    status: str
    notes: str


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


def create_segments_from_records(records: list[Record]) -> tuple[list[CourseSegment], list[dict], str]:
    """
    Create course segments and elevation profile from activity records.

    Returns:
        Tuple of (segments, elevation_profile, notes) where notes contains any warnings.
    """
    notes = []

    # Filter to records with GPS and elevation
    valid_records = [r for r in records if r.lat is not None and r.lon is not None and r.altitude_m is not None]

    if len(valid_records) < 20:
        return [], [], "Insufficient GPS/elevation data"

    # Extract arrays
    distances = np.array([r.distance_m for r in valid_records])
    elevations = np.array([r.altitude_m for r in valid_records])

    # Check for monotonic distance (sometimes records are duplicated)
    if not np.all(np.diff(distances) >= 0):
        # Fix by removing non-monotonic points
        mask = np.concatenate([[True], np.diff(distances) > 0])
        distances = distances[mask]
        elevations = elevations[mask]
        notes.append("Fixed non-monotonic distances")

    if len(distances) < 20:
        return [], [], "Insufficient data after cleanup"

    # Smooth elevation and calculate grades
    smoothed_elevations = smooth_elevation(elevations)
    grades = calculate_grade(distances, smoothed_elevations)

    # Create elevation profile for fine-grained pacing
    elevation_profile = []
    for i, (dist, elev) in enumerate(zip(distances, smoothed_elevations)):
        grade = grades[i] if i < len(grades) else 0.0
        elevation_profile.append({
            "distance_m": float(dist),
            "elevation_m": float(elev),
            "grade_pct": float(grade),
        })

    # Segment the course
    segments = segment_course(distances, grades, smoothed_elevations)

    if not segments:
        return [], elevation_profile, "Segmentation failed"

    return segments, elevation_profile, "; ".join(notes) if notes else ""


def validate_activity(
    activity: Activity,
    segments: list[CourseSegment],
    elevation_profile: list[dict],
    rider_weight_kg: float = 75.0,
    bike_weight_kg: float = 8.0,
    cda: float = 0.32,
    crr: float = 0.004,
) -> ActivityResult:
    """
    Validate pacing model prediction against actual activity data.

    Validates both:
    1. NP/VI prediction (using course punchiness)
    2. Speed/time prediction (using fine-grained pacing engine)
    """
    # Calculate punchiness and expected VI
    punchiness = calculate_course_punchiness(segments)

    # Actual values from activity
    actual_avg = float(activity.avg_power_w)
    actual_np = float(activity.np_power_w)
    actual_vi = actual_np / actual_avg if actual_avg > 0 else 1.0
    actual_time_s = float(activity.elapsed_time_s)
    actual_distance_m = float(activity.total_distance_m)
    actual_avg_speed_mps = actual_distance_m / actual_time_s if actual_time_s > 0 else 0
    actual_avg_speed_kmh = actual_avg_speed_mps * 3.6

    # Predicted NP using VI correction
    pred_vi = punchiness.expected_vi
    pred_np = actual_avg * pred_vi  # Use actual avg power to isolate VI prediction

    # =========================================================================
    # Speed prediction using fine-grained pacing engine
    # =========================================================================
    # Use actual average power as "target" to see how well we predict speed
    total_mass_kg = rider_weight_kg + bike_weight_kg + 3.0  # +3kg for gear
    rider_params = RiderParams(mass_kg=total_mass_kg, cda=cda, crr=crr)

    # Calculate target intensity from actual power and estimated FTP
    # Assume FTP ~ actual_np for tempo-ish efforts, or avg_power * 1.1 for easier
    estimated_ftp = max(actual_np, actual_avg * 1.1)
    target_intensity = actual_avg / estimated_ftp

    # Generate fine-grained prediction
    fine_plan = generate_fine_grained_plan(
        elevation_profile=elevation_profile,
        rider_ftp=estimated_ftp,
        target_intensity=target_intensity,
        rider_params=rider_params,
        env_params=EnvironmentParams(),  # Default sea level
        max_descent_speed_mps=18.0,
        power_cap_ftp_pct=1.5,  # Allow higher for real-world variation
        target_spacing_m=25.0,
    )

    pred_time_s = fine_plan.total_time_s if fine_plan.points else 0
    pred_distance_m = fine_plan.total_distance_m if fine_plan.points else actual_distance_m
    pred_avg_speed_mps = pred_distance_m / pred_time_s if pred_time_s > 0 else 0
    pred_avg_speed_kmh = pred_avg_speed_mps * 3.6

    # Calculate errors
    np_error_pct = abs(pred_np - actual_np) / actual_np * 100 if actual_np > 0 else 0
    vi_error_pct = abs(pred_vi - actual_vi) / actual_vi * 100 if actual_vi > 0 else 0
    speed_error_pct = abs(pred_avg_speed_kmh - actual_avg_speed_kmh) / actual_avg_speed_kmh * 100 if actual_avg_speed_kmh > 0 else 0
    time_error_pct = abs(pred_time_s - actual_time_s) / actual_time_s * 100 if actual_time_s > 0 else 0

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
        pred_vi=pred_vi,
        pred_np=pred_np,
        pred_avg_speed_kmh=pred_avg_speed_kmh,
        pred_time_s=pred_time_s,
        np_error_pct=np_error_pct,
        vi_error_pct=vi_error_pct,
        speed_error_pct=speed_error_pct,
        time_error_pct=time_error_pct,
        grade_stddev=punchiness.grade_stddev,
        steep_climb_fraction=punchiness.steep_climb_fraction,
        rider_mass_kg=total_mass_kg,
        cda=cda,
        crr=crr,
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
                results.append(
                    ActivityResult(
                        activity_id=str(activity.id),
                        activity_title=activity.title or "Untitled",
                        activity_date=activity.started_at.strftime("%Y-%m-%d"),
                        course_type="unknown",
                        total_distance_km=activity.total_distance_m / 1000,
                        elevation_gain_m=activity.elevation_gain_m,
                        elapsed_time_min=activity.elapsed_time_s / 60,
                        actual_avg_power=float(activity.avg_power_w),
                        actual_np=float(activity.np_power_w),
                        actual_vi=float(activity.np_power_w) / float(activity.avg_power_w),
                        actual_avg_speed_kmh=activity.total_distance_m / activity.elapsed_time_s * 3.6 if activity.elapsed_time_s else 0,
                        actual_time_s=float(activity.elapsed_time_s),
                        pred_vi=0,
                        pred_np=0,
                        pred_avg_speed_kmh=0,
                        pred_time_s=0,
                        np_error_pct=0,
                        vi_error_pct=0,
                        speed_error_pct=0,
                        time_error_pct=0,
                        grade_stddev=0,
                        steep_climb_fraction=0,
                        rider_mass_kg=0,
                        cda=0,
                        crr=0,
                        status="skipped",
                        notes="No records found",
                    )
                )
                continue

            # Create segments and elevation profile
            segments, elevation_profile, notes = create_segments_from_records(records)

            if not segments:
                results.append(
                    ActivityResult(
                        activity_id=str(activity.id),
                        activity_title=activity.title or "Untitled",
                        activity_date=activity.started_at.strftime("%Y-%m-%d"),
                        course_type="unknown",
                        total_distance_km=activity.total_distance_m / 1000,
                        elevation_gain_m=activity.elevation_gain_m,
                        elapsed_time_min=activity.elapsed_time_s / 60,
                        actual_avg_power=float(activity.avg_power_w),
                        actual_np=float(activity.np_power_w),
                        actual_vi=float(activity.np_power_w) / float(activity.avg_power_w),
                        actual_avg_speed_kmh=activity.total_distance_m / activity.elapsed_time_s * 3.6 if activity.elapsed_time_s else 0,
                        actual_time_s=float(activity.elapsed_time_s),
                        pred_vi=0,
                        pred_np=0,
                        pred_avg_speed_kmh=0,
                        pred_time_s=0,
                        np_error_pct=0,
                        vi_error_pct=0,
                        speed_error_pct=0,
                        time_error_pct=0,
                        grade_stddev=0,
                        steep_climb_fraction=0,
                        rider_mass_kg=0,
                        cda=0,
                        crr=0,
                        status="skipped",
                        notes=notes,
                    )
                )
                continue

            # Get rider and bike parameters
            rider_weight = await get_user_weight(activity.user_id)
            bike_weight, cda, crr = await get_bike_for_activity(activity)

            # Validate
            result = validate_activity(
                activity,
                segments,
                elevation_profile,
                rider_weight_kg=rider_weight,
                bike_weight_kg=bike_weight,
                cda=cda,
                crr=crr,
            )
            if notes:
                result.notes = notes
            results.append(result)

        except Exception as e:
            logger.error(f"Error processing {activity.id}: {e}")
            results.append(
                ActivityResult(
                    activity_id=str(activity.id),
                    activity_title=activity.title or "Untitled",
                    activity_date=activity.started_at.strftime("%Y-%m-%d"),
                    course_type="unknown",
                    total_distance_km=activity.total_distance_m / 1000,
                    elevation_gain_m=activity.elevation_gain_m,
                    elapsed_time_min=activity.elapsed_time_s / 60,
                    actual_avg_power=float(activity.avg_power_w or 0),
                    actual_np=float(activity.np_power_w or 0),
                    actual_vi=0,
                    actual_avg_speed_kmh=0,
                    actual_time_s=0,
                    pred_vi=0,
                    pred_np=0,
                    pred_avg_speed_kmh=0,
                    pred_time_s=0,
                    np_error_pct=0,
                    vi_error_pct=0,
                    speed_error_pct=0,
                    time_error_pct=0,
                    grade_stddev=0,
                    steep_climb_fraction=0,
                    rider_mass_kg=0,
                    cda=0,
                    crr=0,
                    status="error",
                    notes=str(e),
                )
            )

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
                "pred_vi",
                "pred_np",
                "pred_avg_speed_kmh",
                "pred_time_s",
                "np_error_pct",
                "vi_error_pct",
                "speed_error_pct",
                "time_error_pct",
                "grade_stddev",
                "steep_climb_fraction",
                "rider_mass_kg",
                "cda",
                "crr",
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
                    f"{r.pred_vi:.3f}",
                    f"{r.pred_np:.0f}",
                    f"{r.pred_avg_speed_kmh:.1f}",
                    f"{r.pred_time_s:.0f}",
                    f"{r.np_error_pct:.1f}",
                    f"{r.vi_error_pct:.1f}",
                    f"{r.speed_error_pct:.1f}",
                    f"{r.time_error_pct:.1f}",
                    f"{r.grade_stddev:.2f}",
                    f"{r.steep_climb_fraction:.3f}",
                    f"{r.rider_mass_kg:.1f}",
                    f"{r.cda:.4f}",
                    f"{r.crr:.4f}",
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

    # Overall stats
    np_errors = [r.np_error_pct for r in successful]
    vi_errors = [r.vi_error_pct for r in successful]
    speed_errors = [r.speed_error_pct for r in successful]
    time_errors = [r.time_error_pct for r in successful]

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

    # Actual vs predicted comparison
    actual_speeds = [r.actual_avg_speed_kmh for r in successful]
    pred_speeds = [r.pred_avg_speed_kmh for r in successful]
    actual_times = [r.actual_time_s / 60 for r in successful]  # Convert to minutes
    pred_times = [r.pred_time_s / 60 for r in successful]

    print("\nSpeed Comparison:")
    print(f"  Actual avg: {mean(actual_speeds):.1f} km/h (range: {min(actual_speeds):.1f}-{max(actual_speeds):.1f})")
    print(f"  Predicted avg: {mean(pred_speeds):.1f} km/h (range: {min(pred_speeds):.1f}-{max(pred_speeds):.1f})")

    speed_bias = mean([r.pred_avg_speed_kmh - r.actual_avg_speed_kmh for r in successful])
    print(f"  Bias: {speed_bias:+.1f} km/h (positive = over-predicting speed)")

    # By course type
    print("\n" + "-" * 70)
    print("BY COURSE TYPE")
    print("-" * 70)

    course_types = {r.course_type for r in successful}
    for ct in sorted(course_types):
        ct_results = [r for r in successful if r.course_type == ct]
        ct_np_errors = [r.np_error_pct for r in ct_results]
        ct_speed_errors = [r.speed_error_pct for r in ct_results]
        ct_time_errors = [r.time_error_pct for r in ct_results]

        print(f"\n  {ct.upper()} (n={len(ct_results)}):")
        print(f"    NP Error: mean={mean(ct_np_errors):.1f}%, median={median(ct_np_errors):.1f}%")
        print(f"    Speed Error: mean={mean(ct_speed_errors):.1f}%, median={median(ct_speed_errors):.1f}%")
        print(f"    Time Error: mean={mean(ct_time_errors):.1f}%, median={median(ct_time_errors):.1f}%")

        # Speed bias for this terrain
        ct_speed_bias = mean([r.pred_avg_speed_kmh - r.actual_avg_speed_kmh for r in ct_results])
        print(f"    Speed Bias: {ct_speed_bias:+.1f} km/h")

    # Identify speed outliers (>20% error)
    speed_outliers = [r for r in successful if r.speed_error_pct > 20]
    if speed_outliers:
        print(f"\n" + "-" * 70)
        print(f"SPEED OUTLIERS (error >20%): {len(speed_outliers)}")
        print("-" * 70)
        for r in sorted(speed_outliers, key=lambda x: -x.speed_error_pct)[:5]:
            print(
                f"  {r.activity_title} ({r.activity_date}): "
                f"{r.speed_error_pct:.1f}% error, "
                f"actual={r.actual_avg_speed_kmh:.1f} vs pred={r.pred_avg_speed_kmh:.1f} km/h"
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

    # Speed bias analysis
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
