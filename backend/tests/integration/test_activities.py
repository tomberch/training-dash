import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from fitter.models import Activity, Record  # noqa: E402


class TestActivityEndpoints:
    @pytest.mark.asyncio
    async def test_list_activities_returns_newest_first(self, auth_client):
        for i in range(3):
            fit_data = make_test_fit(num_records=5)
            await auth_client.post(
                "/upload",
                files={"file": (f"test_{i}.fit", fit_data, "application/octet-stream")},
            )
        response = await auth_client.get("/activities")
        assert response.status_code == 200
        activities = response.json()
        assert len(activities) == 3
        dates = [a["started_at"] for a in activities]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.asyncio
    async def test_get_activity_returns_summary_fields(self, auth_client):
        fit_data = make_test_fit(num_records=10)
        upload_resp = await auth_client.post(
            "/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        response = await auth_client.get(f"/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == activity_id
        assert data["total_distance_m"] == 90.0
        assert "started_at" in data
        assert "elevation_gain_m" in data
        assert "avg_speed_mps" in data

    @pytest.mark.asyncio
    async def test_get_activity_records_returns_geojson_for_map(self, auth_client):
        fit_data = make_test_fit(num_records=5)
        upload_resp = await auth_client.post(
            "/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        response = await auth_client.get(f"/activities/{activity_id}/records")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert data["activity_id"] == activity_id
        assert len(data["features"]) == 5
        f0 = data["features"][0]
        assert f0["type"] == "Feature"
        assert f0["geometry"]["type"] == "Point"
        assert f0["geometry"]["coordinates"] is not None
        assert len(f0["geometry"]["coordinates"]) == 2
        assert "distance_m" in f0["properties"]
        assert "hr_bpm" in f0["properties"]
        assert "speed_mps" in f0["properties"]

    @pytest.mark.asyncio
    async def test_get_activity_not_found(self, auth_client):
        response = await auth_client.get("/activities/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_no_gps_still_succeeds_and_records_have_null_geom(
        self, auth_client, db_session
    ):
        fit_data = make_test_fit(num_records=5, include_gps=False)
        response = await auth_client.post(
            "/upload",
            files={"file": ("no_gps.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = response.json()["id"]
        result = await db_session.execute(
            select(Record).where(Record.activity_id == activity_id)
        )
        records = result.scalars().all()
        assert len(records) == 5
        assert all(r.lat is None for r in records)
        assert all(r.lon is None for r in records)
        assert all(r.geom is None for r in records)

    @pytest.mark.asyncio
    async def test_no_gps_activity_summary_still_computed(self, auth_client):
        fit_data = make_test_fit(num_records=5, include_gps=False)
        upload_resp = await auth_client.post(
            "/upload",
            files={"file": ("no_gps.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        response = await auth_client.get(f"/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total_distance_m"] == 40.0
        assert data["avg_hr_bpm"] == 140

    @pytest.mark.asyncio
    async def test_empty_activity_list(self, auth_client):
        response = await auth_client.get("/activities")
        assert response.status_code == 200
        assert response.json() == []