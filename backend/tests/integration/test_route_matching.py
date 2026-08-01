import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from fitter.models import Activity, Route  # noqa: E402


async def upload_and_get_activity(auth_client, db_session, name, fit_data):
    resp = await auth_client.post(
        "/upload",
        files={"file": (name, fit_data, "application/octet-stream")},
    )
    activity_id = resp.json()["id"]
    result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
    return result.scalar_one()


class TestRouteMatching:
    @pytest.mark.asyncio
    async def test_two_rides_same_route_matched_with_low_hausdorff_distance(self, auth_client, db_session):
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        a1 = await upload_and_get_activity(auth_client, db_session, "ride1.fit", fit_data)
        a2 = await upload_and_get_activity(auth_client, db_session, "ride2.fit", fit_data)

        assert a1.route_id is not None
        assert a2.route_id is not None
        assert a1.route_id == a2.route_id

    @pytest.mark.asyncio
    async def test_two_rides_different_routes_not_matched(self, auth_client, db_session):
        fit_a = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        fit_b = make_test_fit(num_records=100, start_lat=46.5197, start_lon=6.6323)
        a1 = await upload_and_get_activity(auth_client, db_session, "route_a.fit", fit_a)
        a2 = await upload_and_get_activity(auth_client, db_session, "route_b.fit", fit_b)

        assert a1.route_id is not None
        assert a2.route_id is not None
        assert a1.route_id != a2.route_id

    @pytest.mark.asyncio
    async def test_out_and_back_rides_matched_to_same_route(self, auth_client, db_session):
        fit_out = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        fit_back = make_test_fit(num_records=200, start_lat=47.3769, start_lon=8.5417, out_and_back=True)
        a1 = await upload_and_get_activity(auth_client, db_session, "out.fit", fit_out)
        a2 = await upload_and_get_activity(auth_client, db_session, "back.fit", fit_back)

        assert a1.route_id is not None
        assert a1.route_id == a2.route_id

    @pytest.mark.asyncio
    async def test_matched_routes_increment_ride_count(self, auth_client, db_session):
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