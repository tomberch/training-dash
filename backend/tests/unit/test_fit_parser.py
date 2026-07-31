import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from generate_fit import make_test_fit  # noqa: E402

from fitter.ingest import parse_records  # noqa: E402


class TestParseRecords:
    def test_parse_record_message_maps_lat_lon_to_degrees(self):
        data = make_test_fit(num_records=3, start_lat=47.3769, start_lon=8.5417)
        parsed = parse_records(data)
        r0 = parsed["records"][0]
        assert abs(r0["lat"] - 47.3769) < 0.001
        assert abs(r0["lon"] - 8.5417) < 0.001

    def test_parse_timestamp_uses_fit_epoch(self):
        data = make_test_fit(num_records=3)
        parsed = parse_records(data)
        assert parsed["records"][0]["timestamp"].year == 2024
        assert parsed["records"][0]["timestamp"].month == 3
        assert parsed["records"][0]["timestamp"].day == 15

    def test_parse_power_in_watts_not_scaled(self):
        data = make_test_fit(num_records=3)
        parsed = parse_records(data)
        assert parsed["records"][0]["power_w"] == 200

    def test_parse_speed_in_m_per_s_not_kmh(self):
        data = make_test_fit(num_records=3)
        parsed = parse_records(data)
        assert abs(parsed["records"][0]["speed_mps"] - 8.0) < 0.01

    def test_parse_heart_rate_bpm_integer(self):
        data = make_test_fit(num_records=3)
        parsed = parse_records(data)
        assert parsed["records"][0]["hr_bpm"] == 120
        assert isinstance(parsed["records"][0]["hr_bpm"], int)

    def test_parse_cadence_rpm_integer(self):
        data = make_test_fit(num_records=3)
        parsed = parse_records(data)
        assert parsed["records"][0]["cadence_rpm"] == 80
        assert isinstance(parsed["records"][0]["cadence_rpm"], int)

    def test_missing_optional_fields_yield_none_not_crash(self):
        data = make_test_fit(num_records=3, include_gps=False)
        parsed = parse_records(data)
        r0 = parsed["records"][0]
        assert r0["lat"] is None
        assert r0["lon"] is None
        assert r0["hr_bpm"] is not None

    def test_lap_messages_have_start_end_timestamps(self):
        data = make_test_fit(num_records=5)
        parsed = parse_records(data)
        assert len(parsed["laps"]) == 1
        lap = parsed["laps"][0]
        assert lap["start_time"].year == 2024
        assert lap["end_time"].year == 2024
        assert lap["start_time"] <= lap["end_time"]

    def test_session_summary_fields(self):
        data = make_test_fit(num_records=5)
        parsed = parse_records(data)
        assert parsed["total_distance_m"] == 40.0
        assert parsed["avg_hr_bpm"] == 140
        assert parsed["avg_power_w"] == 240
        assert parsed["max_speed_mps"] == 12.0
        assert parsed["elevation_gain_m"] == 50.0

    def test_no_gps_activity_still_has_records(self):
        data = make_test_fit(num_records=3, include_gps=False)
        parsed = parse_records(data)
        assert len(parsed["records"]) == 3
        assert all(r["lat"] is None for r in parsed["records"])
        assert all(r["lon"] is None for r in parsed["records"])