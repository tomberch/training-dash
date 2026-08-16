#!/usr/bin/env python3
"""Diagnostic script to check why two activities aren't matching as same route.

Usage:
    uv run python scripts/diagnose_routes.py <activity_id_1> <activity_id_2>
"""

import asyncio
import sys
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from trainingdash.domain.direction import bearings_match
from trainingdash.repositories.postgres.models import Activity, Record, Route
from trainingdash.route_matching import HAUSDORFF_THRESHOLD_M, _meters_to_deg, build_linestring_wkt


async def diagnose(activity_id_1: str, activity_id_2: str):
    engine = create_async_engine("postgresql+asyncpg://trainingdash:trainingdash@localhost:5432/trainingdash")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Load both activities
        result = await session.execute(
            select(Activity).where(Activity.id.in_([UUID(activity_id_1), UUID(activity_id_2)]))
        )
        activities = {str(a.id): a for a in result.scalars().all()}

        if len(activities) != 2:
            print(f"ERROR: Found {len(activities)} activities, expected 2")
            print(f"  Found IDs: {list(activities.keys())}")
            return

        a1 = activities[activity_id_1]
        a2 = activities[activity_id_2]

        print("=" * 60)
        print("ACTIVITY COMPARISON")
        print("=" * 60)
        print()
        print(f"Activity 1: {a1.id}")
        print(f"  Title: {a1.title}")
        print(f"  Route ID: {a1.route_id}")
        print(f"  Direction Bearing (25%): {a1.direction_bearing}")
        print(f"  Direction Bearing (75%): {a1.direction_bearing_75}")
        print(f"  Started: {a1.started_at}")
        print()
        print(f"Activity 2: {a2.id}")
        print(f"  Title: {a2.title}")
        print(f"  Route ID: {a2.route_id}")
        print(f"  Direction Bearing (25%): {a2.direction_bearing}")
        print(f"  Direction Bearing (75%): {a2.direction_bearing_75}")
        print(f"  Started: {a2.started_at}")
        print()

        # Check route_id match
        print("=" * 60)
        print("ROUTE ID ANALYSIS")
        print("=" * 60)
        if a1.route_id == a2.route_id:
            print(f"✓ Same route_id: {a1.route_id}")
        else:
            print(f"✗ Different route_ids: {a1.route_id} vs {a2.route_id}")
            print()
            print("  This means the Hausdorff distance between the GPS tracks")
            print("  exceeded the threshold (100m) when the second activity was ingested.")

        # Check direction bearing match
        print()
        print("=" * 60)
        print("DIRECTION BEARING ANALYSIS")
        print("=" * 60)
        b1_25, b2_25 = a1.direction_bearing, a2.direction_bearing
        b1_75, b2_75 = a1.direction_bearing_75, a2.direction_bearing_75
        match = bearings_match(b1_25, b2_25, b1_75, b2_75)

        print(f"  25% Bearing 1: {b1_25}°" if b1_25 else "  25% Bearing 1: None")
        print(f"  25% Bearing 2: {b2_25}°" if b2_25 else "  25% Bearing 2: None")
        if b1_25 is not None and b2_25 is not None:
            diff_25 = abs(b1_25 - b2_25)
            if diff_25 > 180:
                diff_25 = 360 - diff_25
            print(f"  25% Angular difference: {diff_25}°")
        print()
        print(f"  75% Bearing 1: {b1_75}°" if b1_75 else "  75% Bearing 1: None")
        print(f"  75% Bearing 2: {b2_75}°" if b2_75 else "  75% Bearing 2: None")
        if b1_75 is not None and b2_75 is not None:
            diff_75 = abs(b1_75 - b2_75)
            if diff_75 > 180:
                diff_75 = 360 - diff_75
            print(f"  75% Angular difference: {diff_75}°")
        print()
        print("  Threshold: 90° (both 25% and 75% must match)")
        print(f"  Overall Match: {match}")
        if not match:
            print()
            print("  ✗ Bearings differ by ≥90° at one or both checkpoints.")
            print("    This indicates opposite direction on the route.")
            print("    Possible scenarios:")
            print("    - Opposite direction on an out-and-back route")
            print("    - Clockwise vs counterclockwise on a loop")
            print("    - GPS noise causing bearing variance")

        # Load GPS records and compute actual Hausdorff distance
        print()
        print("=" * 60)
        print("GPS TRACK ANALYSIS")
        print("=" * 60)

        records_1_result = await session.execute(
            select(Record).where(Record.activity_id == a1.id).order_by(Record.timestamp)
        )
        records_2_result = await session.execute(
            select(Record).where(Record.activity_id == a2.id).order_by(Record.timestamp)
        )
        records_1 = list(records_1_result.scalars().all())
        records_2 = list(records_2_result.scalars().all())

        print(f"  Activity 1 GPS points: {len(records_1)}")
        print(f"  Activity 2 GPS points: {len(records_2)}")

        wkt1 = build_linestring_wkt(records_1)
        wkt2 = build_linestring_wkt(records_2)

        if wkt1 and wkt2:
            # Get mid latitude for threshold calculation
            gps_1 = [(r.lat, r.lon) for r in records_1 if r.lat and r.lon]
            gps_2 = [(r.lat, r.lon) for r in records_2 if r.lat and r.lon]
            mid_lat = (sum(lat for lat, _ in gps_1) / len(gps_1) + sum(lat for lat, _ in gps_2) / len(gps_2)) / 2

            tolerance_deg = _meters_to_deg(50.0, mid_lat)
            threshold_deg = _meters_to_deg(HAUSDORFF_THRESHOLD_M, mid_lat)

            # Compute Hausdorff distance between the two tracks
            query = text("""
                SELECT ST_HausdorffDistance(
                    CAST(ST_SetSRID(ST_Simplify(ST_GeomFromText(:wkt1, 4326), :tol), 4326) AS geometry),
                    CAST(ST_SetSRID(ST_Simplify(ST_GeomFromText(:wkt2, 4326), :tol), 4326) AS geometry)
                ) AS distance
            """).params(wkt1=wkt1, wkt2=wkt2, tol=tolerance_deg)

            result = await session.execute(query)
            distance_deg = result.scalar()

            if distance_deg is not None:
                # Convert back to approximate meters
                distance_m = distance_deg * 111000.0 * abs(float(mid_lat)) if mid_lat else distance_deg * 111000.0
                # More accurate conversion
                import math

                distance_m = distance_deg * 111000.0 * math.cos(math.radians(mid_lat))

                print()
                print(f"  Hausdorff distance: {distance_deg:.8f}° ≈ {distance_m:.1f}m")
                print(f"  Threshold: {threshold_deg:.8f}° = {HAUSDORFF_THRESHOLD_M}m")

                if distance_m <= HAUSDORFF_THRESHOLD_M:
                    print("  ✓ Distance is within threshold - tracks SHOULD match")
                    if a1.route_id != a2.route_id:
                        print()
                        print("  ⚠ BUG: Activities have different route_ids despite being within threshold!")
                        print("    Possible causes:")
                        print("    - Route matching ran at different times with different existing routes")
                        print("    - Latitude difference caused different threshold calculations")
                else:
                    print("  ✗ Distance exceeds threshold - tracks correctly don't match")
        else:
            print("  Could not build WKT for one or both activities (missing GPS data)")

        # Check what routes exist
        if a1.route_id or a2.route_id:
            print()
            print("=" * 60)
            print("ROUTE DETAILS")
            print("=" * 60)
            route_ids = [r for r in [a1.route_id, a2.route_id] if r]
            result = await session.execute(select(Route).where(Route.id.in_(route_ids)))
            routes = result.scalars().all()
            for route in routes:
                print(f"  Route {route.id}:")
                print(f"    Ride count: {route.ride_count}")
                print(f"    First seen activity: {route.first_seen_activity_id}")
                print(f"    Created: {route.created_at}")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: uv run python scripts/diagnose_routes.py <activity_id_1> <activity_id_2>")
        sys.exit(1)

    asyncio.run(diagnose(sys.argv[1], sys.argv[2]))
