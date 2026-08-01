import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from fitter.models import Activity  # noqa: E402


class TestRouteMatching:
    @pytest.mark.asyncio
    async def test_two_rides_same_route_matched_with_low_hausdorff_distance(self, auth_client, db_session):
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        resp1 = await auth_client.post(
            "/upload",
            files={"file": ("ride1.fit", fit_data, "application/octet-stream")},
        )
        resp2 = await auth_client.post(
            "/upload",
            files={"file": ("ride2.fit", fit_data, "application/octet-stream")},
        )
        id1 = resp1.json()["id"]
        id2 = resp2.json()["id"]

        result1 = await db_session.execute(select(Activity).where(Activity.id == id1))
        result2 = await db_session.execute(select(Activity).where(Activity.id == id2))
        a1 = result1.scalar_one()
        a2 = result2.scalar_one()

        assert a1.route_id is not None
        assert a2.route_id is not None
        assert a1.route_id == a2.route_id

    @pytest.mark.asyncio
    async def test_two_rides_different_routes_not_matched(self, auth_client, db_session):
        fit_a = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        fit_b = make_test_fit(num_records=100, start_lat=46.5197, start_lon=6.6323)
        resp1 = await auth_client.post(
            "/upload",
            files={"file": ("route_a.fit", fit_a, "application/octet-stream")},
        )
        resp2 = await auth_client.post(
            "/upload",
            files={"file": ("route_b.fit", fit_b, "application/octet-stream")},
        )
        id1 = resp1.json()["id"]
        id2 = resp2.json()["id"]

        result1 = await db_session.execute(select(Activity).where(Activity.id == id1))
        result2 = await db_session.execute(select(Activity).where(Activity.id == id2))
        a1 = result1.scalar_one()
        a2 = result2.scalar_one()

        assert a1.route_id is not None
        assert a2.route_id is not None
        assert a1.route_id != a2.route_id

    @pytest.mark.asyncio
    async def test_out_and_back_rides_matched_to_same_route(self, auth_client, db_session):
        # Out: start to end. Back: same path, reversed.
        fit_out = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417, reverse=False)
        fit_back = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417, reverse=True)
        resp1 = await auth_client.post(
            "/upload",
            files={"file": ("out.fit", fit_out, "application/octet-stream")},
        )
        resp2 = await auth_client.post(
            "/upload",
            files={"file": ("back.fit", fit_back, "application/octet-stream")},
        )
        id1 = resp1.json()["id"]
        id2 = resp2.json()["id"]

        result1 = await db_session.execute(select(Activity).where(Activity.id == id1))
        result2 = await db_session.execute(select(Activity).where(Activity.id == id2))
        a1 = result1.scalar_one()
        a2 = result2.scalar_one()

        assert a1.route_id == a2.route_id

    @pytest.mark.asyncio
    async def test_matched_routes_increment_ride_count(self, auth_client, db_session):
        from fitter.models import Route

        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        await auth_client.post(
            "/upload",
            files={"file": ("ride1.fit", fit_data, "application/octet-stream")},
        )
        await auth_client.post(
            "/upload",
            files={"file": ("ride2.fit", fit_data, "application/octet-stream")},
        )

        result = await db_session.execute(select(Route))
        routes = result.scalars().all()
        assert len(routes) == 1
        assert routes[0].ride_count == 2

    @pytest.mark.asyncio
    async def test_no_gps_activity_has_no_route_id(self, auth_client, db_session):
        fit_data = make_test_fit(num_records=10, include_gps=False)
        resp = await auth_client.post(
            "/upload",
            files={"file": ("no_gps.fit", fit_data, "application/octet-stream")},
        )
        activity_id = resp.json()["id"]
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        assert activity.route_id is None