"""Generate a synthetic FIT file for testing using fit_tool's builder."""
from datetime import datetime, timezone

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage


def make_test_fit(
    num_records: int = 100,
    include_gps: bool = True,
    start_lat: float = 47.3769,
    start_lon: float = 8.5417,
    reverse: bool = False,
    out_and_back: bool = False,
) -> bytes:
    builder = FitFileBuilder()

    start_dt = datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    base_ts_ms = int(start_dt.timestamp() * 1000)

    file_id = FileIdMessage()
    file_id.type = 4  # activity
    file_id.time_created = base_ts_ms
    builder.add(file_id)

    total_distance = 0.0

    for i in range(num_records):
        ts_ms = base_ts_ms + i * 1000
        record = RecordMessage()
        record.timestamp = ts_ms

        if include_gps:
            if out_and_back:
                half = num_records // 2
                if i <= half:
                    offset = i
                else:
                    offset = 2 * half - i
            elif reverse:
                offset = num_records - 1 - i
            else:
                offset = i
            record.position_lat = start_lat + offset * 0.0001
            record.position_long = start_lon + offset * 0.0001

        record.heart_rate = 120 + (i % 40)
        record.cadence = 80 + (i % 20)
        record.power = 200 + (i % 80)
        record.speed = 8.0 + (i * 0.01)
        record.altitude = 500.0 + (i % 5)
        total_distance = i * 10.0
        record.distance = total_distance
        builder.add(record)

    lap_end_ms = base_ts_ms + (num_records - 1) * 1000
    elapsed_s = float(num_records - 1)

    lap = LapMessage()
    lap.timestamp = lap_end_ms
    lap.start_time = base_ts_ms
    lap.total_distance = total_distance
    lap.total_elapsed_time = elapsed_s
    lap.total_moving_time = elapsed_s
    lap.avg_heart_rate = 140
    lap.max_heart_rate = 160
    lap.avg_power = 240
    builder.add(lap)

    session = SessionMessage()
    session.timestamp = lap_end_ms
    session.start_time = base_ts_ms
    session.total_distance = total_distance
    session.total_elapsed_time = elapsed_s
    session.total_moving_time = elapsed_s
    session.total_timer_time = elapsed_s
    session.total_ascent = 50
    session.avg_speed = 8.0
    session.max_speed = 12.0
    session.avg_heart_rate = 140
    session.max_heart_rate = 160
    session.avg_power = 240
    builder.add(session)

    fit = builder.build()
    return fit.to_bytes()