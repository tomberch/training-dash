from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from fitter.models import Activity, Record, Route

HAUSDORFF_THRESHOLD_M = 100.0
# ST_Simplify tolerance in degrees (~50m at equator)
SIMPLIFY_TOLERANCE_DEG = 50.0 / 111000.0
# Hausdorff threshold in degrees (~100m at equator)
HAUSDORFF_THRESHOLD_DEG = 100.0 / 111000.0


def build_linestring_wkt(records: list[Record]) -> str | None:
    points = [(r.lon, r.lat) for r in records if r.lat is not None and r.lon is not None]
    if len(points) < 2:
        return None
    coords = ", ".join(f"{lon} {lat}" for lon, lat in points)
    return f"LINESTRING({coords})"


def _simplified_geometry_sql(expr: str) -> str:
    return f"CAST(ST_SetSRID(ST_Simplify(ST_GeomFromText({expr}, 4326), :tolerance), 4326) AS geometry)"


async def match_route(
    db: AsyncSession,
    activity: Activity,
    records: list[Record],
    threshold_deg: float = HAUSDORFF_THRESHOLD_DEG,
) -> int | None:
    wkt = build_linestring_wkt(records)
    if wkt is None:
        return None

    simplified_expr = _simplified_geometry_sql(":wkt")

    query = text(f"""
        SELECT id, ST_HausdorffDistance(
            {simplified_expr},
            CAST(simplified_polyline AS geometry)
        ) AS distance
        FROM routes
        WHERE user_id = :user_id
        ORDER BY distance
        LIMIT 1
    """).params(wkt=wkt, tolerance=SIMPLIFY_TOLERANCE_DEG, user_id=activity.user_id)

    result = await db.execute(query)
    match = result.first()

    if match is not None and match.distance is not None and match.distance <= threshold_deg:
        route_id = match.id
        await db.execute(
            update(Route).where(Route.id == route_id).values(ride_count=Route.ride_count + 1)
        )
        return route_id

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
        tolerance=SIMPLIFY_TOLERANCE_DEG,
        activity_id=activity.id,
    )
    result = await db.execute(insert_sql)
    route_id = result.scalar()
    return route_id