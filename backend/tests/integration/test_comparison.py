import sys
from pathlib import Path
from uuid import UUID as UUIDType

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit

from trainingdash.repositories.postgres.models import Record


async def upload_fit(auth_client, name, fit_data):
    resp = await auth_client.post(
        "/api/upload",
        files={"file": (name, fit_data, "application/octet-stream")},
    )
    return resp.json()["id"]


class TestCompare:
    @pytest.mark.asyncio
    async def test_two_same_route_rides_return_time_gap_series(self, auth_client):
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        id1 = await upload_fit(auth_client, "ride1.fit", fit_data)
        id2 = await upload_fit(auth_client, "ride2.fit", fit_data)

        response = await auth_client.get(f"/api/activities/{id1}/compare?other={id2}")
        assert response.status_code == 200
        data = response.json()
        assert data["comparable"] is True
        assert len(data["gap_series"]) > 0
        gap0 = data["gap_series"][0]
        assert "distance_m" in gap0
        assert "gap_s" in gap0
        # Same fit data → gap should be ~0 everywhere
        assert abs(gap0["gap_s"]) < 1.0

    @pytest.mark.asyncio
    async def test_gap_signs_correct_faster_ride_negative(self, auth_client, db_session, seed_user):
        from datetime import timedelta

        # Upload two rides on the same route
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        id_a = await upload_fit(auth_client, "ride_a.fit", fit_data)
        id_b = await upload_fit(auth_client, "ride_b.fit", fit_data)

        # Make ride B faster by adjusting its records' timestamps to be closer together
        result_b = await db_session.execute(
            select(Record).where(Record.activity_id == UUIDType(id_b)).order_by(Record.timestamp)
        )
        records_b = result_b.scalars().all()
        base_ts = records_b[0].timestamp
        for i, r in enumerate(records_b):
            r.timestamp = base_ts + timedelta(seconds=i * 0.5)  # half the time → faster
        await db_session.commit()

        response = await auth_client.get(f"/api/activities/{id_a}/compare?other={id_b}")
        data = response.json()
        assert data["comparable"] is True
        gaps = [g["gap_s"] for g in data["gap_series"]]
        # gap = A - B, A is slower → gap should be positive (except at 0m)
        assert gaps[0] == 0
        assert all(g > 0 for g in gaps[1:])

    @pytest.mark.asyncio
    async def test_gap_series_truncates_to_shorter_ride(self, auth_client, db_session, seed_user):

        # Upload same-route rides, then truncate one's records to simulate shorter distance
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        id_long = await upload_fit(auth_client, "long.fit", fit_data)
        id_short = await upload_fit(auth_client, "short.fit", fit_data)

        # Delete last 50 records from id_short to make it shorter
        result = await db_session.execute(
            select(Record).where(Record.activity_id == UUIDType(id_short)).order_by(Record.timestamp)
        )
        records = result.scalars().all()
        for r in records[50:]:
            await db_session.delete(r)
        await db_session.commit()

        response = await auth_client.get(f"/api/activities/{id_long}/compare?other={id_short}")
        data = response.json()
        assert data["comparable"] is True
        # Short ride now has ~490m, long has 990m → truncate at ~490m
        max_dist = max(g["distance_m"] for g in data["gap_series"])
        assert max_dist <= 500.0

    @pytest.mark.asyncio
    async def test_mismatched_routes_return_no_comparison(self, auth_client):
        fit_a = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        fit_b = make_test_fit(num_records=100, start_lat=46.5197, start_lon=6.6323)
        id_a = await upload_fit(auth_client, "route_a.fit", fit_a)
        id_b = await upload_fit(auth_client, "route_b.fit", fit_b)

        response = await auth_client.get(f"/api/activities/{id_a}/compare?other={id_b}")
        data = response.json()
        assert data["comparable"] is False
        assert data["gap_series"] == []

    @pytest.mark.asyncio
    async def test_same_route_picker_returns_other_activities(self, auth_client):
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        id1 = await upload_fit(auth_client, "ride1.fit", fit_data)
        id2 = await upload_fit(auth_client, "ride2.fit", fit_data)
        id3 = await upload_fit(auth_client, "ride3.fit", fit_data)

        response = await auth_client.get(f"/api/activities/{id1}/same-route")
        assert response.status_code == 200
        data = response.json()
        assert data["route_id"] is not None
        ids = [a["id"] for a in data["activities"]]
        assert id2 in ids
        assert id3 in ids
        assert id1 not in ids
