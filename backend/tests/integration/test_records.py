import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from trainingdash.repositories.postgres.models import Activity, User, Route  # noqa: E402
from tests.integration.fixtures import CACHED_HASH_PASS  # noqa: E402


class TestRecords:
    @pytest.mark.asyncio
    async def test_records_returns_lifetime_prs(self, auth_client):
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        await auth_client.post(
            "/api/upload",
            files={"file": ("ride1.fit", fit_data, "application/octet-stream")},
        )
        response = await auth_client.get("/api/records")
        assert response.status_code == 200
        data = response.json()
        lp = data["lifetime_prs"]
        assert lp["longest_distance_m"] is not None
        assert lp["longest_distance_m"]["value"] == 990.0
        assert lp["longest_moving_time_s"] is not None
        assert lp["longest_moving_time_s"]["value"] == 99
        assert lp["max_speed_mps"] is not None
        assert lp["max_speed_mps"]["value"] == 12.0
        assert lp["max_hr_bpm"] is not None
        assert lp["max_hr_bpm"]["value"] == 160
        assert lp["biggest_elevation_gain_m"] is not None
        assert lp["biggest_elevation_gain_m"]["value"] == 50.0
        assert lp["highest_sustained_power_w"] is None
        assert lp["fastest_5000_m"] is None
        assert lp["fastest_10000_m"] is None
        assert lp["fastest_40000_m"] is None

    @pytest.mark.asyncio
    async def test_records_fastest_point_to_point(self, auth_client, db_session, seed_user):
        from datetime import datetime
        for dist, time_s, avg_speed in [(10000, 1200, 10000/1200), (40000, 5400, 40000/5400)]:
            activity = Activity(
                user_id=seed_user.id,
                source="upload",
                source_ref=f"test_{dist}.fit",
                started_at=datetime(2024, 3, 15, 10, 0),
                total_distance_m=dist,
                moving_time_s=time_s,
                avg_speed_mps=avg_speed,
                max_speed_mps=15.0,
                max_hr_bpm=170,
                elevation_gain_m=300,
            )
            db_session.add(activity)
        await db_session.commit()

        response = await auth_client.get("/api/records")
        lp = response.json()["lifetime_prs"]
        assert lp["fastest_5000_m"] is not None
        expected_5k = 5000 / (10000 / 1200)
        assert lp["fastest_5000_m"]["value"] == pytest.approx(expected_5k, rel=0.01)
        assert lp["fastest_5000_m"]["activity_id"] is not None
        assert lp["fastest_10000_m"] is not None
        assert lp["fastest_10000_m"]["value"] == pytest.approx(1200, rel=0.01)
        assert lp["fastest_40000_m"] is not None
        assert lp["fastest_40000_m"]["value"] == pytest.approx(5400, rel=0.01)

    @pytest.mark.asyncio
    async def test_records_cross_user_isolation(self, auth_client, db_session, seed_user):
        from datetime import datetime

        activity_a = Activity(
            user_id=seed_user.id,
            source="upload",
            source_ref="a.fit",
            started_at=datetime(2024, 3, 15, 10, 0),
            total_distance_m=10000,
            moving_time_s=1800,
            avg_speed_mps=10000/1800,
            max_speed_mps=12.0,
            max_hr_bpm=160,
            elevation_gain_m=200,
        )
        db_session.add(activity_a)

        user_b = User(email="userb@example.com", password_hash=CACHED_HASH_PASS)
        db_session.add(user_b)
        await db_session.commit()
        await db_session.refresh(user_b)

        activity_b = Activity(
            user_id=user_b.id,
            source="upload",
            source_ref="b.fit",
            started_at=datetime(2024, 3, 15, 10, 0),
            total_distance_m=99999,
            moving_time_s=99999,
            avg_speed_mps=50.0,
            max_speed_mps=99.0,
            max_hr_bpm=199,
            elevation_gain_m=999,
        )
        db_session.add(activity_b)
        await db_session.commit()

        response = await auth_client.get("/api/records")
        lp = response.json()["lifetime_prs"]
        assert lp["longest_distance_m"]["value"] == 10000
        assert lp["longest_moving_time_s"]["value"] == 1800
        assert lp["max_speed_mps"]["value"] == 12.0
        assert lp["max_hr_bpm"]["value"] == 160
        assert lp["biggest_elevation_gain_m"]["value"] == 200
        assert lp["fastest_40000_m"] is None

    @pytest.mark.asyncio
    async def test_records_empty(self, auth_client):
        response = await auth_client.get("/api/records")
        assert response.status_code == 200
        data = response.json()
        assert data["lifetime_prs"]["longest_distance_m"] is None
        assert data["lifetime_prs"]["max_speed_mps"] is None
        assert data["lifetime_prs"]["fastest_5000_m"] is None
        assert data["lifetime_prs"]["highest_sustained_power_w"] is None
        assert data["route_prs"] == []

    @pytest.mark.asyncio
    async def test_per_route_prs_faster_ride_holds_record(self, auth_client, db_session, seed_user):
        from datetime import datetime
        # Upload two rides on the same route
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        resp1 = await auth_client.post(
            "/api/upload",
            files={"file": ("ride1.fit", fit_data, "application/octet-stream")},
        )
        resp2 = await auth_client.post(
            "/api/upload",
            files={"file": ("ride2.fit", fit_data, "application/octet-stream")},
        )
        id1 = resp1.json()["id"]
        id2 = resp2.json()["id"]

        # Make ride 2 faster by setting a lower elapsed_time
        result = await db_session.execute(select(Activity).where(Activity.id == id2))
        activity2 = result.scalar_one()
        activity2.elapsed_time_s = 60  # faster
        await db_session.commit()

        response = await auth_client.get("/api/records")
        data = response.json()
        route_prs = data["route_prs"]
        assert len(route_prs) == 1
        assert route_prs[0]["fastest_time_s"] == 60
        assert route_prs[0]["activity_id"] == id2

    @pytest.mark.asyncio
    async def test_per_route_prs_cross_user_isolation(self, auth_client, db_session, seed_user):
        from datetime import datetime
        # User A uploads a ride
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        await auth_client.post(
            "/api/upload",
            files={"file": ("ride_a.fit", fit_data, "application/octet-stream")},
        )

        # User B uploads a ride on a different route
        user_b = User(email="userb@example.com", password_hash=CACHED_HASH_PASS)
        db_session.add(user_b)
        await db_session.commit()
        await db_session.refresh(user_b)

        fit_b = make_test_fit(num_records=100, start_lat=46.5197, start_lon=6.6323)
        from trainingdash.ingest import ingest_fit
        await ingest_fit(db_session, user_b.id, fit_b, "upload", "ride_b.fit")

        response = await auth_client.get("/api/records")
        data = response.json()
        route_prs = data["route_prs"]
        # User A should only see their own route, not user B's
        assert len(route_prs) == 1
        assert route_prs[0]["route_id"] is not None