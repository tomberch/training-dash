#!/usr/bin/env python3
"""
Validate per-segment power predictions against real ride data.

Compares the terrain-adapted power formula (power_mult = 1.10 + 0.057 × grade%)
against actual power recorded in activities to validate per-segment accuracy.

Usage:
    python scripts/validate_segment_power.py [--output results.csv] [--user-id N]
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

from trainingdash.domain.pacing import (
    GRADE_POWER_INTERCEPT,
    GRADE_POWER_SLOPE,
    MIN_POWER_MULTIPLIER,
    MAX_POWER_MULTIPLIER,
    get_grade_power_multiplier,
)
from trainingdash.domain.elevation import smooth_elevation
from trainingdash.domain.grade import calculate_grade
from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Activity, Record

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class GradeBucket:
    """Accumulated data for a grade bucket."""
    grade_center: float  # Center of grade bucket (e.g., -5%, 0%, 5%)
    total_time_s: float  # Total time in this grade bucket
    actual_power_sum: float  # Sum of power × time for weighted average
    predicted_mult_sum: float  # Sum of predicted multiplier × time
    sample_count: int  # Number of data points


@dataclass
class ActivityPowerResult:
    """Result of power validation for one activity."""
    activity_id: str
    activity_title: str
    activity_date: str
    total_distance_km: float
    avg_power: float
    # Per-grade-bucket results
    grade_buckets: list[GradeBucket]
    # Overall accuracy
    mean_error_pct: float
    status: str
    notes: str


async def get_activities_with_power(user_id: int | None = None) -> list[Activity]:
    """Get all activities with measured power data."""
    async with async_session() as db:
        query = (
            select(Activity)
            .where(
                Activity.avg_power_w.isnot(None),
                Activity.total_distance_m > 5000,  # At least 5km
                Activity.elapsed_time_s > 1200,  # At least 20 minutes
                Activity.power_source == "measured",  # Only actual power meters
                Activity.elevation_gain_m > 100,  # Must have some climbing
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
        result = await db.execute(
            select(Record)
            .where(Record.activity_id == activity_id)
            .order_by(Record.distance_m)
        )
        return list(result.scalars().all())


def bucket_grade(grade_pct: float, bucket_size: float = 2.0) -> float:
    """Round grade to nearest bucket center."""
    return round(grade_pct / bucket_size) * bucket_size


def analyze_power_by_grade(
    records: list[Record],
    avg_power: float,
) -> tuple[list[GradeBucket], str]:
    """
    Analyze actual vs predicted power by grade.
    
    Returns:
        Tuple of (grade_buckets, notes)
    """
    notes = []
    
    # Filter to records with power, GPS, and elevation
    valid = [
        r for r in records
        if r.power_w is not None and r.power_w > 0
        and r.lat is not None and r.lon is not None
        and r.altitude_m is not None
        and r.timestamp is not None
    ]
    
    if len(valid) < 50:
        return [], "Insufficient valid records"
    
    # Sort by timestamp
    valid = sorted(valid, key=lambda r: r.timestamp)
    
    # Calculate grades between consecutive points
    # Accumulate data by grade bucket
    buckets: dict[float, GradeBucket] = {}
    
    for i in range(1, len(valid)):
        prev = valid[i - 1]
        curr = valid[i]
        
        # Calculate grade from elevation change
        distance_delta = curr.distance_m - prev.distance_m
        if distance_delta < 1:  # Skip if no distance change
            continue
            
        elevation_delta = curr.altitude_m - prev.altitude_m
        grade_pct = (elevation_delta / distance_delta) * 100
        
        # Clamp extreme grades (GPS noise)
        grade_pct = max(-20, min(20, grade_pct))
        
        # Time delta (assume 1s if not available)
        time_delta = 1.0
        if prev.timestamp and curr.timestamp:
            time_delta = max(0.5, min(10, (curr.timestamp - prev.timestamp).total_seconds()))
        
        # Power for this segment (use average of two points)
        power = (prev.power_w + curr.power_w) / 2
        
        # Bucket the grade
        bucket_center = bucket_grade(grade_pct)
        
        if bucket_center not in buckets:
            buckets[bucket_center] = GradeBucket(
                grade_center=bucket_center,
                total_time_s=0,
                actual_power_sum=0,
                predicted_mult_sum=0,
                sample_count=0,
            )
        
        bucket = buckets[bucket_center]
        bucket.total_time_s += time_delta
        bucket.actual_power_sum += power * time_delta
        
        # Calculate predicted multiplier for this grade
        pred_mult = get_grade_power_multiplier(grade_pct)
        bucket.predicted_mult_sum += pred_mult * time_delta
        bucket.sample_count += 1
    
    # Convert to list sorted by grade
    bucket_list = sorted(buckets.values(), key=lambda b: b.grade_center)
    
    return bucket_list, "; ".join(notes) if notes else ""


async def validate_activity_power(activity: Activity) -> ActivityPowerResult:
    """Validate power predictions for one activity."""
    
    records = await get_records_for_activity(str(activity.id))
    
    if not records:
        return ActivityPowerResult(
            activity_id=str(activity.id),
            activity_title=activity.title or "Untitled",
            activity_date=activity.started_at.strftime("%Y-%m-%d"),
            total_distance_km=activity.total_distance_m / 1000,
            avg_power=float(activity.avg_power_w),
            grade_buckets=[],
            mean_error_pct=0,
            status="skipped",
            notes="No records found",
        )
    
    avg_power = float(activity.avg_power_w)
    buckets, notes = analyze_power_by_grade(records, avg_power)
    
    if not buckets:
        return ActivityPowerResult(
            activity_id=str(activity.id),
            activity_title=activity.title or "Untitled",
            activity_date=activity.started_at.strftime("%Y-%m-%d"),
            total_distance_km=activity.total_distance_m / 1000,
            avg_power=avg_power,
            grade_buckets=[],
            mean_error_pct=0,
            status="skipped",
            notes=notes or "Analysis failed",
        )
    
    # Calculate mean error across buckets (weighted by time)
    total_time = sum(b.total_time_s for b in buckets)
    
    errors = []
    for b in buckets:
        if b.total_time_s < 10:  # Skip buckets with < 10s of data
            continue
            
        actual_power = b.actual_power_sum / b.total_time_s
        actual_mult = actual_power / avg_power if avg_power > 0 else 1.0
        pred_mult = b.predicted_mult_sum / b.total_time_s
        
        error_pct = abs(pred_mult - actual_mult) / actual_mult * 100 if actual_mult > 0 else 0
        errors.append((error_pct, b.total_time_s))
    
    if errors:
        weighted_error = sum(e * t for e, t in errors) / sum(t for _, t in errors)
    else:
        weighted_error = 0
    
    return ActivityPowerResult(
        activity_id=str(activity.id),
        activity_title=activity.title or "Untitled",
        activity_date=activity.started_at.strftime("%Y-%m-%d"),
        total_distance_km=activity.total_distance_m / 1000,
        avg_power=avg_power,
        grade_buckets=buckets,
        mean_error_pct=weighted_error,
        status="success",
        notes=notes,
    )


async def run_validation(
    user_id: int | None = None,
    output_path: str = "segment_power_validation.csv",
) -> None:
    """Run power validation across all qualifying activities."""
    
    logger.info("Starting segment power validation...")
    
    activities = await get_activities_with_power(user_id)
    logger.info(f"Found {len(activities)} activities with power data and climbing")
    
    results: list[ActivityPowerResult] = []
    
    # Aggregate data across all activities by grade
    global_buckets: dict[float, dict] = {}
    
    for i, activity in enumerate(activities):
        logger.info(f"Processing {i + 1}/{len(activities)}: {activity.title or activity.id}")
        
        try:
            result = await validate_activity_power(activity)
            results.append(result)
            
            # Accumulate global stats
            if result.status == "success":
                for b in result.grade_buckets:
                    if b.grade_center not in global_buckets:
                        global_buckets[b.grade_center] = {
                            "total_time": 0,
                            "actual_power_sum": 0,
                            "pred_mult_sum": 0,
                            "avg_power_sum": 0,
                        }
                    
                    global_buckets[b.grade_center]["total_time"] += b.total_time_s
                    global_buckets[b.grade_center]["actual_power_sum"] += b.actual_power_sum
                    global_buckets[b.grade_center]["pred_mult_sum"] += b.predicted_mult_sum
                    global_buckets[b.grade_center]["avg_power_sum"] += result.avg_power * b.total_time_s
        
        except Exception as e:
            logger.error(f"Error processing {activity.id}: {e}")
            results.append(ActivityPowerResult(
                activity_id=str(activity.id),
                activity_title=activity.title or "Untitled",
                activity_date=activity.started_at.strftime("%Y-%m-%d"),
                total_distance_km=activity.total_distance_m / 1000,
                avg_power=float(activity.avg_power_w or 0),
                grade_buckets=[],
                mean_error_pct=0,
                status="error",
                notes=str(e),
            ))
    
    # Print summary
    print_summary(results, global_buckets)
    
    # Write detailed CSV
    write_csv(results, global_buckets, output_path)


def print_summary(
    results: list[ActivityPowerResult],
    global_buckets: dict[float, dict],
) -> None:
    """Print validation summary."""
    
    successful = [r for r in results if r.status == "success"]
    
    print("\n" + "=" * 80)
    print("SEGMENT POWER VALIDATION SUMMARY")
    print("=" * 80)
    print(f"\nTotal activities: {len(results)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Skipped/Error: {len(results) - len(successful)}")
    
    if not successful:
        print("\nNo successful validations.")
        return
    
    # Overall accuracy
    mean_errors = [r.mean_error_pct for r in successful if r.mean_error_pct > 0]
    if mean_errors:
        print(f"\nOverall Power Prediction Error (per activity):")
        print(f"  Mean: {mean(mean_errors):.1f}%")
        print(f"  Median: {median(mean_errors):.1f}%")
        if len(mean_errors) > 1:
            print(f"  Std Dev: {stdev(mean_errors):.1f}%")
    
    # Global analysis by grade
    print("\n" + "-" * 80)
    print("POWER MULTIPLIER BY GRADE (aggregated across all activities)")
    print("-" * 80)
    print(f"\nFormula: power_mult = {GRADE_POWER_INTERCEPT:.2f} + {GRADE_POWER_SLOPE:.3f} × grade%")
    print(f"Bounds: [{MIN_POWER_MULTIPLIER:.2f}, {MAX_POWER_MULTIPLIER:.2f}]")
    print()
    print(f"{'Grade':>8}  {'Time':>8}  {'Actual':>8}  {'Predicted':>10}  {'Error':>8}")
    print(f"{'(%)':>8}  {'(min)':>8}  {'Mult':>8}  {'Mult':>10}  {'(%)':>8}")
    print("-" * 50)
    
    total_weighted_error = 0
    total_time = 0
    
    for grade in sorted(global_buckets.keys()):
        data = global_buckets[grade]
        time_min = data["total_time"] / 60
        
        if data["total_time"] < 60:  # Skip grades with < 1 min of data
            continue
        
        actual_power = data["actual_power_sum"] / data["total_time"]
        avg_power = data["avg_power_sum"] / data["total_time"]
        actual_mult = actual_power / avg_power if avg_power > 0 else 1.0
        
        pred_mult = data["pred_mult_sum"] / data["total_time"]
        
        error_pct = abs(pred_mult - actual_mult) / actual_mult * 100 if actual_mult > 0 else 0
        
        total_weighted_error += error_pct * data["total_time"]
        total_time += data["total_time"]
        
        print(f"{grade:>8.0f}  {time_min:>8.1f}  {actual_mult:>8.2f}  {pred_mult:>10.2f}  {error_pct:>8.1f}")
    
    if total_time > 0:
        overall_error = total_weighted_error / total_time
        print("-" * 50)
        print(f"{'TOTAL':>8}  {total_time/60:>8.1f}  {'':>8}  {'':>10}  {overall_error:>8.1f}")
    
    # Regression recommendation
    print("\n" + "-" * 80)
    print("REGRESSION ANALYSIS")
    print("-" * 80)
    
    # Calculate best-fit linear coefficients from data
    grades = []
    actual_mults = []
    weights = []
    
    for grade, data in global_buckets.items():
        if data["total_time"] < 60:
            continue
        actual_power = data["actual_power_sum"] / data["total_time"]
        avg_power = data["avg_power_sum"] / data["total_time"]
        actual_mult = actual_power / avg_power if avg_power > 0 else 1.0
        
        grades.append(grade)
        actual_mults.append(actual_mult)
        weights.append(data["total_time"])
    
    if len(grades) >= 3:
        # Weighted linear regression
        grades = np.array(grades)
        actual_mults = np.array(actual_mults)
        weights = np.array(weights)
        
        # Weighted least squares: minimize sum(w * (y - (a + b*x))^2)
        W = np.sum(weights)
        sum_wx = np.sum(weights * grades)
        sum_wy = np.sum(weights * actual_mults)
        sum_wxx = np.sum(weights * grades * grades)
        sum_wxy = np.sum(weights * grades * actual_mults)
        
        denom = W * sum_wxx - sum_wx * sum_wx
        if abs(denom) > 1e-10:
            slope = (W * sum_wxy - sum_wx * sum_wy) / denom
            intercept = (sum_wy - slope * sum_wx) / W
            
            print(f"\nBest-fit formula from data:")
            print(f"  power_mult = {intercept:.3f} + {slope:.4f} × grade%")
            print(f"\nCurrent formula:")
            print(f"  power_mult = {GRADE_POWER_INTERCEPT:.3f} + {GRADE_POWER_SLOPE:.4f} × grade%")
            
            # Calculate if update is needed
            intercept_diff = abs(intercept - GRADE_POWER_INTERCEPT)
            slope_diff = abs(slope - GRADE_POWER_SLOPE)
            
            if intercept_diff > 0.05 or slope_diff > 0.01:
                print(f"\nRecommendation: Consider updating coefficients")
                print(f"  Intercept change: {intercept - GRADE_POWER_INTERCEPT:+.3f}")
                print(f"  Slope change: {slope - GRADE_POWER_SLOPE:+.4f}")
            else:
                print(f"\nCurrent coefficients are well-calibrated.")


def write_csv(
    results: list[ActivityPowerResult],
    global_buckets: dict[float, dict],
    output_path: str,
) -> None:
    """Write validation results to CSV."""
    
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        
        # Global summary section
        writer.writerow(["GLOBAL SUMMARY BY GRADE"])
        writer.writerow(["grade_pct", "time_min", "actual_mult", "predicted_mult", "error_pct"])
        
        for grade in sorted(global_buckets.keys()):
            data = global_buckets[grade]
            time_min = data["total_time"] / 60
            
            if data["total_time"] < 60:
                continue
            
            actual_power = data["actual_power_sum"] / data["total_time"]
            avg_power = data["avg_power_sum"] / data["total_time"]
            actual_mult = actual_power / avg_power if avg_power > 0 else 1.0
            pred_mult = data["pred_mult_sum"] / data["total_time"]
            error_pct = abs(pred_mult - actual_mult) / actual_mult * 100 if actual_mult > 0 else 0
            
            writer.writerow([f"{grade:.0f}", f"{time_min:.1f}", f"{actual_mult:.3f}", f"{pred_mult:.3f}", f"{error_pct:.1f}"])
        
        writer.writerow([])
        
        # Per-activity section
        writer.writerow(["PER-ACTIVITY RESULTS"])
        writer.writerow(["activity_id", "title", "date", "distance_km", "avg_power", "mean_error_pct", "status", "notes"])
        
        for r in results:
            writer.writerow([
                r.activity_id,
                r.activity_title,
                r.activity_date,
                f"{r.total_distance_km:.1f}",
                f"{r.avg_power:.0f}",
                f"{r.mean_error_pct:.1f}",
                r.status,
                r.notes,
            ])
    
    logger.info(f"Results written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Validate segment power predictions")
    parser.add_argument("--output", "-o", default="segment_power_validation.csv", help="Output CSV path")
    parser.add_argument("--user-id", "-u", type=int, help="Filter to specific user ID")
    args = parser.parse_args()
    
    asyncio.run(run_validation(user_id=args.user_id, output_path=args.output))


if __name__ == "__main__":
    main()
