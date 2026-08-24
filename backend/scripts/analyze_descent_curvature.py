#!/usr/bin/env python3
"""
Analyze how much road curvature explains descent speed variance.

Research question: Is cornering behavior worth modeling for pacing predictions?

Approach:
1. Extract descent segments (grade < -2%) from activities
2. Calculate road curvature from GPS points
3. Compare models:
   - Model A: speed ~ grade only
   - Model B: speed ~ grade + curvature
4. Measure R² improvement to quantify curvature's value

Usage:
    python scripts/analyze_descent_curvature.py [--user-id N]
"""

import argparse
import asyncio
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select

from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Activity, Record

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DescentPoint:
    """A single point on a descent with all relevant data."""

    activity_id: str
    distance_m: float
    speed_mps: float
    grade_pct: float
    curvature: float  # 1/radius in 1/m, higher = tighter turn
    power_w: float


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS points in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def calculate_curvature(p1: tuple, p2: tuple, p3: tuple) -> float:
    """
    Calculate curvature at p2 given three consecutive GPS points.

    Uses the Menger curvature formula: k = 4A / (|p1-p2| x |p2-p3| x |p1-p3|)
    where A is the area of the triangle formed by the three points.

    Returns curvature in 1/meters (higher = tighter turn).
    """
    # Convert to local cartesian (approximate for small distances)
    lat1, lon1 = p1
    lat2, lon2 = p2
    lat3, lon3 = p3

    # Use p2 as origin, convert to meters
    # 1 degree latitude ≈ 111,000 m
    # 1 degree longitude ≈ 111,000 × cos(lat) m
    lat_to_m = 111000
    lon_to_m = 111000 * math.cos(math.radians(lat2))

    x1 = (lon1 - lon2) * lon_to_m
    y1 = (lat1 - lat2) * lat_to_m
    x2 = 0
    y2 = 0
    x3 = (lon3 - lon2) * lon_to_m
    y3 = (lat3 - lat2) * lat_to_m

    # Side lengths
    a = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)  # p1 to p2
    b = math.sqrt((x3 - x2) ** 2 + (y3 - y2) ** 2)  # p2 to p3
    c = math.sqrt((x3 - x1) ** 2 + (y3 - y1) ** 2)  # p1 to p3

    if a < 1 or b < 1 or c < 1:
        return 0.0  # Points too close

    # Area using cross product
    area = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2

    if area < 0.01:
        return 0.0  # Nearly collinear (straight road)

    # Menger curvature
    curvature = 4 * area / (a * b * c)

    return curvature


async def get_activities_with_descents(user_id: int | None = None) -> list[Activity]:
    """Get activities with significant descending."""
    async with async_session() as db:
        query = (
            select(Activity)
            .where(
                Activity.total_distance_m > 10000,  # At least 10km
                Activity.elevation_loss_m > 200,  # At least 200m descending
                Activity.avg_speed_mps.isnot(None),
            )
            .order_by(Activity.started_at.desc())
            .limit(30)  # Limit for performance
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


def extract_descent_points(records: list[Record], activity_id: str) -> list[DescentPoint]:
    """Extract descent points with curvature from activity records."""

    # Filter to records with GPS, speed, and elevation
    valid = [
        r
        for r in records
        if r.lat is not None
        and r.lon is not None
        and r.altitude_m is not None
        and r.speed_mps is not None
        and r.speed_mps > 2  # Moving
    ]

    if len(valid) < 10:
        return []

    # Sort by distance
    valid = sorted(valid, key=lambda r: r.distance_m)

    points: list[DescentPoint] = []

    for i in range(2, len(valid) - 2):
        # Use 5-point window for smoothing
        prev2 = valid[i - 2]
        prev1 = valid[i - 1]
        curr = valid[i]
        next1 = valid[i + 1]
        next2 = valid[i + 2]

        # Calculate grade from elevation change
        dist_delta = next1.distance_m - prev1.distance_m
        if dist_delta < 5:
            continue

        elev_delta = next1.altitude_m - prev1.altitude_m
        grade_pct = (elev_delta / dist_delta) * 100

        # Only descents (grade < -2%)
        if grade_pct > -2:
            continue

        # Calculate curvature using 3 points
        curvature = calculate_curvature(
            (prev1.lat, prev1.lon),
            (curr.lat, curr.lon),
            (next1.lat, next1.lon),
        )

        # Skip extreme curvatures (likely GPS noise)
        if curvature > 0.1:  # Radius < 10m is unrealistic for cycling
            continue

        points.append(
            DescentPoint(
                activity_id=activity_id,
                distance_m=curr.distance_m,
                speed_mps=curr.speed_mps,
                grade_pct=grade_pct,
                curvature=curvature,
                power_w=curr.power_w or 0,
            )
        )

    return points


def analyze_variance(points: list[DescentPoint]) -> dict:
    """
    Analyze how much variance in descent speed is explained by grade vs grade+curvature.

    Returns R² for both models and the improvement.
    """
    if len(points) < 50:
        return {"error": "Insufficient data points"}

    # Extract arrays
    speeds = np.array([p.speed_mps for p in points])
    grades = np.array([p.grade_pct for p in points])
    curvatures = np.array([p.curvature for p in points])

    # Standardize for regression
    speed_mean, speed_std = np.mean(speeds), np.std(speeds)
    grade_mean, grade_std = np.mean(grades), np.std(grades)
    curv_mean, curv_std = np.mean(curvatures), np.std(curvatures) if np.std(curvatures) > 0 else 1

    # Total variance in speed
    ss_total = np.sum((speeds - speed_mean) ** 2)

    # Model A: speed ~ grade (linear regression)
    # Using normal equations: β = (X'X)^(-1) X'y
    X_a = np.column_stack([np.ones(len(grades)), grades])
    beta_a = np.linalg.lstsq(X_a, speeds, rcond=None)[0]
    pred_a = X_a @ beta_a
    ss_res_a = np.sum((speeds - pred_a) ** 2)
    r2_grade_only = 1 - (ss_res_a / ss_total)

    # Model B: speed ~ grade + curvature
    X_b = np.column_stack([np.ones(len(grades)), grades, curvatures])
    beta_b = np.linalg.lstsq(X_b, speeds, rcond=None)[0]
    pred_b = X_b @ beta_b
    ss_res_b = np.sum((speeds - pred_b) ** 2)
    r2_grade_curvature = 1 - (ss_res_b / ss_total)

    # Model C: speed ~ grade + curvature + grade*curvature (interaction)
    interactions = grades * curvatures
    X_c = np.column_stack([np.ones(len(grades)), grades, curvatures, interactions])
    beta_c = np.linalg.lstsq(X_c, speeds, rcond=None)[0]
    pred_c = X_c @ beta_c
    ss_res_c = np.sum((speeds - pred_c) ** 2)
    r2_with_interaction = 1 - (ss_res_c / ss_total)

    # Curvature coefficient interpretation
    # Negative coefficient means higher curvature = lower speed (expected)
    curvature_coef = beta_b[2]

    return {
        "n_points": len(points),
        "speed_mean_mps": float(speed_mean),
        "speed_std_mps": float(speed_std),
        "grade_mean_pct": float(grade_mean),
        "curvature_mean": float(curv_mean),
        "curvature_std": float(curv_std),
        "r2_grade_only": float(r2_grade_only),
        "r2_grade_curvature": float(r2_grade_curvature),
        "r2_with_interaction": float(r2_with_interaction),
        "r2_improvement_from_curvature": float(r2_grade_curvature - r2_grade_only),
        "curvature_coefficient": float(curvature_coef),
        "grade_coefficient": float(beta_b[1]),
        "intercept": float(beta_b[0]),
    }


async def run_analysis(user_id: int | None = None) -> None:
    """Run the curvature analysis."""

    logger.info("Starting descent curvature analysis...")

    activities = await get_activities_with_descents(user_id)
    logger.info(f"Found {len(activities)} activities with significant descents")

    all_points: list[DescentPoint] = []

    for i, activity in enumerate(activities):
        logger.info(f"Processing {i + 1}/{len(activities)}: {activity.title or activity.id}")

        records = await get_records_for_activity(str(activity.id))
        points = extract_descent_points(records, str(activity.id))
        all_points.extend(points)

        logger.info(f"  Found {len(points)} descent points")

    logger.info(f"\nTotal descent points: {len(all_points)}")

    if len(all_points) < 100:
        print("\nInsufficient data for analysis. Need at least 100 descent points.")
        return

    # Run analysis
    results = analyze_variance(all_points)

    # Print results
    print("\n" + "=" * 70)
    print("DESCENT CURVATURE ANALYSIS")
    print("=" * 70)

    print("\nData summary:")
    print(f"  Total descent points: {results['n_points']:,}")
    print(f"  Mean descent speed: {results['speed_mean_mps']:.1f} m/s ({results['speed_mean_mps'] * 3.6:.1f} km/h)")
    print(f"  Speed std dev: {results['speed_std_mps']:.1f} m/s")
    print(f"  Mean grade: {results['grade_mean_pct']:.1f}%")
    print(f"  Mean curvature: {results['curvature_mean']:.5f} (1/m)")
    if results["curvature_mean"] > 0:
        print(f"  Mean turn radius: {1 / results['curvature_mean']:.0f} m")

    print("\n" + "-" * 70)
    print("VARIANCE EXPLAINED (R²)")
    print("-" * 70)

    print(
        f"\n  Model A (grade only):           R² = {results['r2_grade_only']:.3f} ({results['r2_grade_only'] * 100:.1f}%)"
    )
    print(
        f"  Model B (grade + curvature):    R² = {results['r2_grade_curvature']:.3f} ({results['r2_grade_curvature'] * 100:.1f}%)"
    )
    print(
        f"  Model C (+ interaction):        R² = {results['r2_with_interaction']:.3f} ({results['r2_with_interaction'] * 100:.1f}%)"
    )

    improvement = results["r2_improvement_from_curvature"]
    print(f"\n  Improvement from curvature: {improvement:.3f} ({improvement * 100:.1f}% additional variance explained)")

    print("\n" + "-" * 70)
    print("INTERPRETATION")
    print("-" * 70)

    if improvement < 0.02:
        print("\n  Curvature explains <2% additional variance.")
        print("  RECOMMENDATION: NOT worth modeling cornering behavior.")
        print("  Grade alone is sufficient for descent speed prediction.")
    elif improvement < 0.10:
        print(f"\n  Curvature explains {improvement * 100:.1f}% additional variance.")
        print("  RECOMMENDATION: MARGINAL value. Consider if complexity is justified.")
    else:
        print(f"\n  Curvature explains {improvement * 100:.1f}% additional variance.")
        print("  RECOMMENDATION: WORTH modeling cornering behavior.")

    print("\n  Regression coefficients (Model B):")
    print(
        f"    speed = {results['intercept']:.2f} + {results['grade_coefficient']:.3f}*grade + {results['curvature_coefficient']:.1f}*curvature"
    )

    if results["curvature_coefficient"] < 0:
        print("\n  Curvature coefficient is negative (expected): tighter turns = slower speed")
        # Convert to practical terms
        # If curvature = 0.01 (100m radius), how much speed reduction?
        speed_reduction_100m = abs(results["curvature_coefficient"]) * 0.01
        speed_reduction_50m = abs(results["curvature_coefficient"]) * 0.02
        print(f"    100m radius turn: {speed_reduction_100m:.1f} m/s slower ({speed_reduction_100m * 3.6:.1f} km/h)")
        print(f"    50m radius turn: {speed_reduction_50m:.1f} m/s slower ({speed_reduction_50m * 3.6:.1f} km/h)")

    # Additional analysis: by curvature buckets
    print("\n" + "-" * 70)
    print("SPEED BY CURVATURE BUCKET")
    print("-" * 70)

    # Bucket by curvature (turn radius)
    straight = [p for p in all_points if p.curvature < 0.002]  # >500m radius
    gentle = [p for p in all_points if 0.002 <= p.curvature < 0.005]  # 200-500m
    moderate = [p for p in all_points if 0.005 <= p.curvature < 0.01]  # 100-200m
    tight = [p for p in all_points if 0.01 <= p.curvature < 0.02]  # 50-100m
    hairpin = [p for p in all_points if p.curvature >= 0.02]  # <50m

    print(f"\n  {'Curvature':<20} {'Radius':<15} {'Count':<10} {'Avg Speed':<15}")
    print(f"  {'-' * 60}")

    for name, bucket, radius_desc in [
        ("Straight", straight, ">500m"),
        ("Gentle curve", gentle, "200-500m"),
        ("Moderate curve", moderate, "100-200m"),
        ("Tight curve", tight, "50-100m"),
        ("Hairpin", hairpin, "<50m"),
    ]:
        if bucket:
            avg_speed = mean([p.speed_mps for p in bucket])
            print(f"  {name:<20} {radius_desc:<15} {len(bucket):<10} {avg_speed:.1f} m/s ({avg_speed * 3.6:.1f} km/h)")
        else:
            print(f"  {name:<20} {radius_desc:<15} {'0':<10} {'N/A':<15}")


def main():
    parser = argparse.ArgumentParser(description="Analyze descent curvature impact on speed")
    parser.add_argument("--user-id", "-u", type=int, help="Filter to specific user ID")
    args = parser.parse_args()

    asyncio.run(run_analysis(user_id=args.user_id))


if __name__ == "__main__":
    main()
