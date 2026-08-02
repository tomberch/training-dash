import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from trainingdash.models import Activity, Lap, Record  # noqa: E402


class TestUpload:
    @pytest.mark.asyncio
    async def test_upload_fit_returns_201_and_activity_id(self, auth_client):
        fit_data = make_test_fit(num_records=10)
        response = await auth_client.post(
            "/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert isinstance(data["id"], int)
        assert "started_at" in data

    @pytest.mark.asyncio
    async def test_uploaded_fit_writes_activity_summary_row(self, auth_client, db_session):
        fit_data = make_test_fit(num_records=10)
        response = await auth_client.post(
            "/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = response.json()["id"]
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        assert activity.total_distance_m == 90.0
        assert activity.avg_hr_bpm == 140
        assert activity.avg_power_w == 240
        assert activity.max_speed_mps == 12.0
        assert activity.elevation_gain_m == 50.0
        assert activity.source == "upload"
        assert activity.source_ref == "test.fit"

    @pytest.mark.asyncio
    async def test_uploaded_fit_writes_records_with_lat_lon_hr_power_alt(
        self, auth_client, db_session
    ):
        fit_data = make_test_fit(num_records=5)
        response = await auth_client.post(
            "/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = response.json()["id"]
        result = await db_session.execute(
            select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp)
        )
        records = result.scalars().all()
        assert len(records) == 5
        r0 = records[0]
        assert abs(r0.lat - 47.3769) < 0.001
        assert abs(r0.lon - 8.5417) < 0.001
        assert r0.hr_bpm == 120
        assert r0.power_w == 200
        assert r0.altitude_m == 500.0
        assert r0.geom is not None

    @pytest.mark.asyncio
    async def test_uploaded_fit_writes_laps(self, auth_client, db_session):
        fit_data = make_test_fit(num_records=10)
        response = await auth_client.post(
            "/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = response.json()["id"]
        result = await db_session.execute(
            select(Lap).where(Lap.activity_id == activity_id).order_by(Lap.lap_index)
        )
        laps = result.scalars().all()
        assert len(laps) == 1
        assert laps[0].lap_index == 0
        assert laps[0].avg_hr_bpm == 140
        assert laps[0].avg_power_w == 240
        assert laps[0].max_hr_bpm == 160

    @pytest.mark.asyncio
    async def test_uploaded_fit_stores_raw_bytes(self, auth_client, db_session):
        fit_data = make_test_fit(num_records=5)
        response = await auth_client.post(
            "/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = response.json()["id"]
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        assert activity.raw_fit is not None
        assert len(activity.raw_fit) == len(fit_data)

    @pytest.mark.asyncio
    async def test_upload_requires_auth(self, app_client):
        fit_data = make_test_fit(num_records=5)
        response = await app_client.post(
            "/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 401