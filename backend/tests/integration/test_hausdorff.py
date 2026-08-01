import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_identical_polylines_hausdorff_distance_zero(db_session: AsyncSession):
    wkt = "LINESTRING(0 0, 1 1, 2 2)"
    stmt = text("SELECT ST_HausdorffDistance(CAST(:a AS geometry), CAST(:b AS geometry)) AS dist").params(a=wkt, b=wkt)
    result = await db_session.execute(stmt)
    distance = result.scalar()
    assert distance == 0.0


@pytest.mark.asyncio
async def test_parallel_offset_polylines_distance_equals_offset(db_session: AsyncSession):
    wkt_a = "LINESTRING(0 0, 10 0)"
    wkt_b = "LINESTRING(0 5, 10 5)"
    stmt = text("SELECT ST_HausdorffDistance(CAST(:a AS geometry), CAST(:b AS geometry)) AS dist").params(a=wkt_a, b=wkt_b)
    result = await db_session.execute(stmt)
    distance = result.scalar()
    assert distance == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_st_simplify_reduces_point_count(db_session: AsyncSession):
    wkt = "LINESTRING(0 0, 1 0, 2 0, 3 0, 4 0, 5 0, 6 0, 7 0, 8 0, 9 0, 10 0)"
    stmt = text("SELECT ST_NPoints(ST_Simplify(CAST(:geom AS geometry), 1.0)) AS n").params(geom=wkt)
    result = await db_session.execute(stmt)
    simplified_count = result.scalar()

    stmt2 = text("SELECT ST_NPoints(CAST(:geom AS geometry)) AS n").params(geom=wkt)
    result2 = await db_session.execute(stmt2)
    original_count = result2.scalar()
    assert simplified_count < original_count