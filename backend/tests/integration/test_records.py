import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from fitter.models import Activity, User  # noqa: E402
from fitter.auth import hash_password  # noqa: E402


class TestRecords:
    @pytest.mark.asyncio
    async def test_records_returns_lifetime_prs(self, auth_client):
        fit_data = make_test_fit(num_records=100, start_lat=47.3769, start_lon=8.5417)
        await auth_client.post(
            "/upload",
            files={"file": ("ride1.fit", fit_data, "application/octet-stream")},
        )
        response = await auth_client.get("/records")
        assert response.status_code == 200
        data = response.json()
        assert data["longest_distance_m"] is not None
        assert data["longest_distance_m"]["value"] == 990.0
        assert data["max_speed_mps"] is not None
        assert data["max_hr_bpm"] is not None
        assert data["max_hr_bpm"]["value"] == 160
        assert data["biggest_elevation_gain_m"] is not None
        assert data["biggest_elevation_gain_m"]["value"] == 50.0

    @pytest.mark.asyncio
    async def test_records_fastest_point_to_point(self, auth_client, db_session, seed_user):
        # Create activities with known distances and times
        from datetime import datetime
        for dist, time_s in [(5000, 600), (10000, 1200), (40000, 5400)]:
            activity = Activity(
                user_id=seed_user.id,
                source="upload",
                source_ref=f"test_{dist}.fit",
                started_at=datetime(2024, 3, 15, 10, 0),
                total_distance_m=dist,
                moving_time_s=time_s,
                max_speed_mps=15.0,
                max_hr_bpm=170,
                elevation_gain_m=300,
            )
            db_session.add(activity)
        await db_session.commit()

        response = await auth_client.get("/records")
        data = response.json()
        assert data["fastest_5000_m"] is not None
        assert data["fastest_5000_m"]["value"] == 600
        assert data["fastest_10000_m"] is not None
        assert data["fastest_10000_m"]["value"] == 1200
        assert data["fastest_40000_m"] is not None
        assert data["fastest_40000_m"]["value"] == 5400

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
            max_speed_mps=12.0,
            max_hr_bpm=160,
            elevation_gain_m=200,
        )
        db_session.add(activity_a)

        user_b = User(username="userb", password_hash=hash_password("passb"))
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
            max_speed_mps=99.0,
            max_hr_bpm=199,
            elevation_gain_m=999,
        )
        db_session.add(activity_b)
        await db_session.commit()

        response = await auth_client.get("/records")
        data = response.json()
        # User A's records should not include user B's extreme values
        assert data["longest_distance_m"]["value"] == 10000
        assert data["max_hr_bpm"]["value"] == 160
        assert data["biggest_elevation_gain_m"]["value"] == 200

    @pytest.mark.asyncio
    async def test_records_empty(self, auth_client):
        response = await auth_client.get("/records")
        assert response.status_code == 200
        data = response.json()
        assert data["longest_distance_m"] is None
        assert data["max_speed_mps"] is None
        assert data["fastest_5000_m"] is None