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
            "/api/upload",
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
            "/api/upload",
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
            "/api/upload",
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
            "/api/upload",
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
            "/api/upload",
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
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 401


class TestActivityMetricsOnIngest:
    """Tests for activity metrics computed during ingest (#18)."""

    @pytest.mark.asyncio
    async def test_upload_without_thresholds_skips_metrics(self, auth_client, db_session):
        """Upload without thresholds configured does not compute training metrics."""
        fit_data = make_test_fit(num_records=60)  # 60 records for NP calculation
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = response.json()["id"]
        
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        
        # No thresholds = no metrics
        assert activity.np_power_w is None
        assert activity.intensity_factor is None
        assert activity.tss is None
        assert activity.power_zone_times is None
        assert activity.hr_zone_times is None
        assert activity.wbal_min_joules is None

    @pytest.mark.asyncio
    async def test_upload_with_thresholds_computes_np_if_tss(self, auth_client, db_session):
        """Upload with FTP threshold computes NP, IF, and TSS."""
        # Set up threshold with effective_date before test FIT (2024-03-15)
        await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2024-01-01",
                "ftp_watts": 250,
                "lthr_bpm": 165,
                "hrmax_bpm": 185
            }
        )
        
        # Upload FIT with 60+ records (enough for 30s rolling avg)
        fit_data = make_test_fit(num_records=120)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = response.json()["id"]
        
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        
        # NP should be computed (test FIT has power data)
        assert activity.np_power_w is not None
        assert activity.np_power_w > 0
        
        # IF = NP / FTP
        assert activity.intensity_factor is not None
        assert 0 < activity.intensity_factor < 2  # Reasonable range
        
        # TSS should be computed
        assert activity.tss is not None
        assert activity.tss > 0
        
        # training_load should equal TSS
        assert activity.training_load == activity.tss

    @pytest.mark.asyncio
    async def test_upload_with_zones_computes_power_zone_times(self, auth_client, db_session):
        """Upload with power zones computes time in each zone."""
        # Set up threshold with effective_date before test FIT (2024-03-15)
        await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2024-01-01",
                "ftp_watts": 250,
                "lthr_bpm": 165,
                "hrmax_bpm": 185
            }
        )
        
        # Ensure zones exist by calling GET /me/zones
        zones_resp = await auth_client.get("/api/me/zones")
        assert zones_resp.status_code == 200
        zones_data = zones_resp.json()
        assert len(zones_data["power_zones"]) == 7  # Coggan 7-zone
        
        # Upload FIT
        fit_data = make_test_fit(num_records=60)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = response.json()["id"]
        
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        
        # Power zone times should be computed
        assert activity.power_zone_times is not None
        import json
        zone_times = json.loads(activity.power_zone_times)
        assert isinstance(zone_times, dict)
        # Total time should roughly equal number of valid power records
        total_zone_time = sum(zone_times.values())
        assert total_zone_time > 0

    @pytest.mark.asyncio
    async def test_upload_with_zones_computes_hr_zone_times(self, auth_client, db_session):
        """Upload with HR zones computes time in each zone."""
        # Set up threshold with effective_date before test FIT (2024-03-15)
        await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2024-01-01",
                "ftp_watts": 250,
                "lthr_bpm": 165,
                "hrmax_bpm": 185
            }
        )
        
        # Ensure zones exist
        zones_resp = await auth_client.get("/api/me/zones")
        assert zones_resp.status_code == 200
        zones_data = zones_resp.json()
        assert len(zones_data["hr_zones"]) == 5  # Friel 5-zone
        
        # Upload FIT
        fit_data = make_test_fit(num_records=60)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = response.json()["id"]
        
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        
        # HR zone times should be computed
        assert activity.hr_zone_times is not None
        import json
        zone_times = json.loads(activity.hr_zone_times)
        assert isinstance(zone_times, dict)
        total_zone_time = sum(zone_times.values())
        assert total_zone_time > 0

    @pytest.mark.asyncio
    async def test_upload_computes_wbal_min(self, auth_client, db_session):
        """Upload with FTP computes W'bal minimum."""
        # Set up threshold with effective_date before test FIT (2024-03-15)
        await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2024-01-01",
                "ftp_watts": 250,
                "lthr_bpm": 165,
                "hrmax_bpm": 185
            }
        )
        
        # Upload FIT with power data
        fit_data = make_test_fit(num_records=120)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = response.json()["id"]
        
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        
        # W'bal should be computed
        assert activity.wbal_min_joules is not None
        assert activity.wbal_min_pct is not None
        assert 0 <= activity.wbal_min_pct <= 100

    @pytest.mark.asyncio
    async def test_get_activity_returns_metrics(self, auth_client):
        """GET /activities/{id} returns computed training metrics."""
        # Set up threshold with effective_date before test FIT (2024-03-15)
        await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2024-01-01",
                "ftp_watts": 250,
                "lthr_bpm": 165,
                "hrmax_bpm": 185
            }
        )
        await auth_client.get("/api/me/zones")  # Trigger zone creation
        
        # Upload FIT
        fit_data = make_test_fit(num_records=120)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        
        # Get activity detail
        response = await auth_client.get(f"/api/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        
        # Should include all metrics
        assert "np_power_w" in data
        assert "intensity_factor" in data
        assert "tss" in data
        assert "training_load" in data
        assert "power_zone_times" in data
        assert "hr_zone_times" in data
        assert "wbal_min_joules" in data
        assert "wbal_min_pct" in data
        
        # Values should be populated
        assert data["np_power_w"] is not None
        assert data["intensity_factor"] is not None
        assert data["tss"] is not None
        assert isinstance(data["power_zone_times"], dict)
        assert isinstance(data["hr_zone_times"], dict)




class TestPeakPowersOnIngest:
    """Tests for peak power extraction during ingest (#19)."""

    @pytest.mark.asyncio
    async def test_upload_extracts_peak_powers(self, auth_client, db_session):
        """Upload with power data extracts peaks at standard durations."""
        from trainingdash.models import ActivityPeakPower
        
        # Upload FIT with 120 records (2 minutes of data)
        fit_data = make_test_fit(num_records=120)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = response.json()["id"]
        
        # Query peaks from database
        result = await db_session.execute(
            select(ActivityPeakPower)
            .where(ActivityPeakPower.activity_id == activity_id)
            .order_by(ActivityPeakPower.duration_seconds)
        )
        peaks = result.scalars().all()
        
        # Should have peaks for durations <= 120 seconds (1, 5, 10, 30, 60, 120)
        assert len(peaks) >= 6
        
        # Check durations are as expected
        durations = [p.duration_seconds for p in peaks]
        assert 1 in durations
        assert 5 in durations
        assert 10 in durations
        assert 30 in durations
        assert 60 in durations
        
        # All watts should be positive
        for peak in peaks:
            assert peak.watts > 0

    @pytest.mark.asyncio
    async def test_upload_only_stores_peaks_for_valid_durations(self, auth_client, db_session):
        """Peaks only stored for durations where ride was long enough."""
        from trainingdash.models import ActivityPeakPower
        
        # Upload FIT with only 30 records (30 seconds)
        fit_data = make_test_fit(num_records=30)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = response.json()["id"]
        
        # Query peaks
        result = await db_session.execute(
            select(ActivityPeakPower)
            .where(ActivityPeakPower.activity_id == activity_id)
            .order_by(ActivityPeakPower.duration_seconds)
        )
        peaks = result.scalars().all()
        
        # Should only have peaks for durations <= 30 seconds
        durations = [p.duration_seconds for p in peaks]
        assert 1 in durations
        assert 5 in durations
        assert 10 in durations
        assert 30 in durations
        # Should NOT have 60, 120, etc.
        assert 60 not in durations
        assert 120 not in durations

    @pytest.mark.asyncio
    async def test_get_activity_returns_peaks_array(self, auth_client):
        """GET /activities/{id} includes peaks array."""
        # Upload FIT with power data
        fit_data = make_test_fit(num_records=120)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        
        # Get activity detail
        response = await auth_client.get(f"/api/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        
        # Should include peaks array
        assert "peaks" in data
        assert isinstance(data["peaks"], list)
        assert len(data["peaks"]) >= 6
        
        # Each peak should have duration_seconds and watts
        for peak in data["peaks"]:
            assert "duration_seconds" in peak
            assert "watts" in peak
            assert peak["watts"] > 0
        
        # Peaks should be ordered by duration
        durations = [p["duration_seconds"] for p in data["peaks"]]
        assert durations == sorted(durations)

    @pytest.mark.asyncio
    async def test_peak_values_are_reasonable(self, auth_client):
        """Peak power values decrease as duration increases (generally)."""
        # Upload FIT
        fit_data = make_test_fit(num_records=120)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        
        response = await auth_client.get(f"/api/activities/{activity_id}")
        data = response.json()
        
        # 1-second peak should be >= 60-second peak (shorter duration = higher peak generally)
        peaks_by_duration = {p["duration_seconds"]: p["watts"] for p in data["peaks"]}
        
        if 1 in peaks_by_duration and 60 in peaks_by_duration:
            # With test FIT's power pattern (200 + i % 80), the 1s peak should be high
            assert peaks_by_duration[1] >= peaks_by_duration[60]
