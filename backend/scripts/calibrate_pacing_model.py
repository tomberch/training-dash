#!/usr/bin/env python3
"""
Calibration pipeline for pacing model validation.

Validates and calibrates the pacing model against real ride data from all
activities with power data. Runs entirely in-memory - no database writes.

Usage:
    python scripts/calibrate_pacing_model.py [--output results.csv] [--user-id N]
"""

import argparse
import asyncio
import csv
import logging
import sys
from dataclasses import dataclass
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
from trainingdash.domain.grade import calculate_grade
from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Activity, Record, User

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
    # Predicted values
    pred_vi: float
    pred_np: float
    # Errors
    np_error_pct: float
    vi_error_pct: float
    # Punchiness details
    grade_stddev: float
    steep_climb_fraction: float
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


def create_segments_from_records(records: list[Record]) -> tuple[list[CourseSegment], str]:
    """
    Create course segments from activity records.

    Returns:
        Tuple of (segments, notes) where notes contains any warnings.
    """
    notes = []

    # Filter to records with GPS and elevation
    valid_records = [r for r in records if r.lat is not None and r.lon is not None and r.altitude_m is not None]

    if len(valid_records) < 20:
        return [], "Insufficient GPS/elevation data"

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
        return [], "Insufficient data after cleanup"

    # Smooth elevation and calculate grades
    smoothed_elevations = smooth_elevation(elevations)
    grades = calculate_grade(distances, smoothed_elevations)

    # Segment the course
    segments = segment_course(distances, grades, smoothed_elevations)

    if not segments:
        return [], "Segmentation failed"

    return segments, "; ".join(notes) if notes else ""


def validate_activity(
    activity: Activity,
    segments: list[CourseSegment],
    rider_weight_kg: float = 75.0,
) -> ActivityResult:
    """
    Validate pacing model prediction against actual activity data.
    """
    # Calculate punchiness and expected VI
    punchiness = calculate_course_punchiness(segments)

    # Actual values from activity
    actual_avg = float(activity.avg_power_w)
    actual_np = float(activity.np_power_w)
    actual_vi = actual_np / actual_avg if actual_avg > 0 else 1.0

    # Predicted NP using VI correction
    pred_vi = punchiness.expected_vi
    pred_np = actual_avg * pred_vi  # Use actual avg power to isolate VI prediction

    # Calculate errors
    np_error_pct = abs(pred_np - actual_np) / actual_np * 100 if actual_np > 0 else 0
    vi_error_pct = abs(pred_vi - actual_vi) / actual_vi * 100 if actual_vi > 0 else 0

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
        pred_vi=pred_vi,
        pred_np=pred_np,
        np_error_pct=np_error_pct,
        vi_error_pct=vi_error_pct,
        grade_stddev=punchiness.grade_stddev,
        steep_climb_fraction=punchiness.steep_climb_fraction,
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
                        pred_vi=0,
                        pred_np=0,
                        np_error_pct=0,
                        vi_error_pct=0,
                        grade_stddev=0,
                        steep_climb_fraction=0,
                        status="skipped",
                        notes="No records found",
                    )
                )
                continue

            # Create segments
            segments, notes = create_segments_from_records(records)

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
                        pred_vi=0,
                        pred_np=0,
                        np_error_pct=0,
                        vi_error_pct=0,
                        grade_stddev=0,
                        steep_climb_fraction=0,
                        status="skipped",
                        notes=notes,
                    )
                )
                continue

            # Validate
            result = validate_activity(activity, segments)
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
                    pred_vi=0,
                    pred_np=0,
                    np_error_pct=0,
                    vi_error_pct=0,
                    grade_stddev=0,
                    steep_climb_fraction=0,
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
                "pred_vi",
                "pred_np",
                "np_error_pct",
                "vi_error_pct",
                "grade_stddev",
                "steep_climb_fraction",
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
                    f"{r.pred_vi:.3f}",
                    f"{r.pred_np:.0f}",
                    f"{r.np_error_pct:.1f}",
                    f"{r.vi_error_pct:.1f}",
                    f"{r.grade_stddev:.2f}",
                    f"{r.steep_climb_fraction:.3f}",
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

    print("\nOverall NP Error:")
    print(f"  Mean: {mean(np_errors):.1f}%")
    print(f"  Median: {median(np_errors):.1f}%")
    print(f"  Std Dev: {stdev(np_errors):.1f}%" if len(np_errors) > 1 else "  Std Dev: N/A")
    print(f"  Min: {min(np_errors):.1f}%")
    print(f"  Max: {max(np_errors):.1f}%")

    print("\nOverall VI Error:")
    print(f"  Mean: {mean(vi_errors):.1f}%")
    print(f"  Median: {median(vi_errors):.1f}%")
    print(f"  Std Dev: {stdev(vi_errors):.1f}%" if len(vi_errors) > 1 else "  Std Dev: N/A")

    # By course type
    print("\nBy Course Type:")
    course_types = {r.course_type for r in successful}
    for ct in sorted(course_types):
        ct_results = [r for r in successful if r.course_type == ct]
        ct_np_errors = [r.np_error_pct for r in ct_results]
        ct_vi_errors = [r.vi_error_pct for r in ct_results]
        print(f"\n  {ct.upper()} (n={len(ct_results)}):")
        print(f"    NP Error: mean={mean(ct_np_errors):.1f}%, median={median(ct_np_errors):.1f}%")
        print(f"    VI Error: mean={mean(ct_vi_errors):.1f}%, median={median(ct_vi_errors):.1f}%")

        # Show actual vs predicted VI for this type
        actual_vis = [r.actual_vi for r in ct_results]
        pred_vis = [r.pred_vi for r in ct_results]
        print(f"    Actual VI: mean={mean(actual_vis):.3f}, range=[{min(actual_vis):.3f}, {max(actual_vis):.3f}]")
        print(f"    Pred VI:   mean={mean(pred_vis):.3f}, range=[{min(pred_vis):.3f}, {max(pred_vis):.3f}]")

    # Identify outliers (>20% NP error)
    outliers = [r for r in successful if r.np_error_pct > 20]
    if outliers:
        print(f"\nOutliers (NP error >20%): {len(outliers)}")
        for r in sorted(outliers, key=lambda x: -x.np_error_pct)[:5]:
            print(
                f"  {r.activity_title} ({r.activity_date}): {r.np_error_pct:.1f}% error, VI actual={r.actual_vi:.3f} vs pred={r.pred_vi:.3f}"
            )

    # Coefficient recommendations
    print("\n" + "-" * 70)
    print("COEFFICIENT ANALYSIS")
    print("-" * 70)

    # Calculate systematic bias
    vi_biases = [r.pred_vi - r.actual_vi for r in successful]
    mean_bias = mean(vi_biases)
    print(f"\nVI Prediction Bias: {mean_bias:+.3f} (positive = over-predicting)")

    if abs(mean_bias) > 0.02:
        print(f"  Recommendation: Adjust base VI by {-mean_bias:+.3f}")
    else:
        print("  Bias is within acceptable range.")

    # Check if steep climbs need adjustment
    mountain_results = [r for r in successful if r.course_type == "mountain"]
    if mountain_results:
        mountain_bias = mean([r.pred_vi - r.actual_vi for r in mountain_results])
        print(f"\nMountain course VI bias: {mountain_bias:+.3f}")
        if abs(mountain_bias) > 0.03:
            print("  Consider adjusting steep climb coefficients")


def main():
    parser = argparse.ArgumentParser(description="Calibrate pacing model against real ride data")
    parser.add_argument("--output", "-o", default="calibration_results.csv", help="Output CSV path")
    parser.add_argument("--user-id", "-u", type=int, help="Filter to specific user ID")
    args = parser.parse_args()

    asyncio.run(run_calibration(user_id=args.user_id, output_path=args.output))


if __name__ == "__main__":
    main()
