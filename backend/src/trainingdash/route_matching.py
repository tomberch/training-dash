import math

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Activity, Record, Route

HAUSDORFF_THRESHOLD_M = 100.0
SIMPLIFY_TOLERANCE_M = 50.0


def _meters_to_deg(meters: float, lat: float) -> float:
    return meters / (111000.0 * math.cos(math.radians(lat)))


def build_linestring_wkt(records: list[Record] | list[dict]) -> str | None:
    def get_lat_lon(r):
        if isinstance(r, dict):
            return r.get("lat"), r.get("lon")
        return r.lat, r.lon

    points = [get_lat_lon(r) for r in records]
    points = [(lon, lat) for lat, lon in points if lat is not None and lon is not None]
    if len(points) < 2:
        return None
    coords = ", ".join(f"{lon} {lat}" for lon, lat in points)
    return f"LINESTRING({coords})"


def _simplified_geometry_sql(expr: str) -> str:
    return f"CAST(ST_SetSRID(ST_Simplify(ST_GeomFromText({expr}, 4326), :tolerance), 4326) AS geometry)"


async def find_or_create_route_id(
    db: AsyncSession,
    activity: Activity,
    records: list[Record],
    threshold_m: float = HAUSDORFF_THRESHOLD_M,
) -> int | None:
    """
    Find an existing route matching this activity's GPS track, or create a new one.
    
    Uses Hausdorff distance to compare simplified polylines. If a match is found
    within threshold, increments the route's ride_count. Otherwise creates a new route.
    
    Returns the route_id or None if the activity has no GPS data.
    """
    wkt = build_linestring_wkt(records)
    if wkt is None:
        return None

    gps_records = [(r["lat"], r["lon"]) if isinstance(r, dict) else (r.lat, r.lon)
                   for r in records
                   if (r.get("lat") if isinstance(r, dict) else r.lat) is not None
                   and (r.get("lon") if isinstance(r, dict) else r.lon) is not None]
    if not gps_records:
        return None
    mid_lat = sum(lat for lat, lon in gps_records) / len(gps_records)
    tolerance_deg = _meters_to_deg(SIMPLIFY_TOLERANCE_M, mid_lat)
    threshold_deg = _meters_to_deg(threshold_m, mid_lat)

    simplified_expr = _simplified_geometry_sql(":wkt")

    # Find closest matching route
    query = text(f"""
        SELECT id, ST_HausdorffDistance(
            {simplified_expr},
            CAST(simplified_polyline AS geometry)
        ) AS distance
        FROM routes
        WHERE user_id = :user_id
        ORDER BY distance
        LIMIT 1
    """).params(wkt=wkt, tolerance=tolerance_deg, user_id=activity.user_id)

    result = await db.execute(query)
    rows = result.all()  # Fully consume result to release asyncpg cursor
    match = rows[0] if rows else None

    if match is not None and match.distance is not None and match.distance <= threshold_deg:
        # Found a matching route - increment ride count
        route_id = match.id
        await db.execute(
            update(Route).where(Route.id == route_id).values(ride_count=Route.ride_count + 1)
        )
        await db.flush()
        return route_id

    # No match found - create new route
    insert_sql = text(f"""
        INSERT INTO routes (user_id, simplified_polyline, first_seen_activity_id, ride_count)
        VALUES (:user_id,
                CAST({simplified_expr} AS geography),
                :activity_id,
                1)
        RETURNING id
    """).params(
        user_id=activity.user_id,
        wkt=wkt,
        tolerance=tolerance_deg,
        activity_id=activity.id,
    )
    result = await db.execute(insert_sql)
    route_id = result.scalar_one()
    await db.flush()
    return route_id