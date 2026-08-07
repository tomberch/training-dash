"""
Generate synthetic FIT files for testing using fit_tool's builder.

This module provides two main functions:
- make_test_fit(): Simple FIT file with configurable GPS and record count
- make_test_fit_with_profile(): FIT file with precise power profile for CP model testing

Power Profile Format
--------------------
Intervals are specified as a list of (duration_seconds, power_watts) tuples:

    intervals = [
        (300, 150),   # 5 min warmup at 150W
        (300, 270),   # 5 min effort at 270W (this becomes peak 5-min power)
        (300, 120),   # 5 min cooldown at 120W
    ]

The generator creates 1-second records with the specified power for each interval.
GPS coordinates progress linearly to create a valid route.

CP Model Verification
---------------------
To generate FIT files that produce specific CP/W' values when analyzed:

    CP model: P(t) = CP + W'/t

For CP=220W, W'=15000J:
- P(120s) = 220 + 15000/120 = 345W
- P(300s) = 220 + 15000/300 = 270W
- P(600s) = 220 + 15000/600 = 245W

Create intervals with these exact power values at corresponding durations.
"""
from datetime import datetime, timezone
from typing import Sequence

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage


# Type alias for power profile intervals
PowerInterval = tuple[int, int]  # (duration_seconds, power_watts)


def make_test_fit_with_profile(
    intervals: Sequence[PowerInterval],
    start_time: datetime | None = None,
    include_gps: bool = True,
    start_lat: float = 47.3769,
    start_lon: float = 8.5417,
    include_hr: bool = True,
    include_cadence: bool = True,
) -> bytes:
    """
    Generate a FIT file with a specific power profile.

    Creates 1-second records with power values matching the specified intervals.
    This allows generating test files that produce predictable peak power values
    when analyzed by the power curve extraction code.

    Args:
        intervals: List of (duration_seconds, power_watts) tuples defining the
            power profile. Each interval generates `duration_seconds` records
            at exactly `power_watts`.
        start_time: Activity start time (default: 2024-03-15 10:00:00 UTC)
        include_gps: Whether to include GPS coordinates (default: True)
        start_lat: Starting latitude for GPS track (default: Zurich)
        start_lon: Starting longitude for GPS track (default: Zurich)
        include_hr: Whether to include heart rate data (default: True)
        include_cadence: Whether to include cadence data (default: True)

    Returns:
        FIT file as bytes

    Example:
        # Generate a ride with a 5-min effort at 270W
        fit_bytes = make_test_fit_with_profile([
            (300, 150),   # 5 min warmup at 150W
            (300, 270),   # 5 min effort at 270W (peak 5-min power)
            (300, 120),   # 5 min cooldown at 120W
        ])

        # Generate a ride for CP model testing (CP=220W, W'=15000J)
        fit_bytes = make_test_fit_with_profile([
            (60, 100),    # warmup
            (120, 345),   # 2-min effort: 220 + 15000/120 = 345W
            (60, 100),    # recovery
            (300, 270),   # 5-min effort: 220 + 15000/300 = 270W
            (60, 100),    # recovery
            (600, 245),   # 10-min effort: 220 + 15000/600 = 245W
            (60, 100),    # cooldown
        ])
    """
    if not intervals:
        raise ValueError("intervals must not be empty")

    builder = FitFileBuilder()

    start_dt = start_time or datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    base_ts_ms = int(start_dt.timestamp() * 1000)

    # File ID message
    file_id = FileIdMessage()
    file_id.type = 4  # activity
    file_id.time_created = base_ts_ms
    builder.add(file_id)

    # Generate records for each interval
    record_index = 0
    total_distance = 0.0
    total_power_sum = 0
    max_power = 0
    max_hr = 0

    for duration_s, power_w in intervals:
        for _ in range(duration_s):
            ts_ms = base_ts_ms + record_index * 1000
            record = RecordMessage()
            record.timestamp = ts_ms

            # GPS: linear progression
            if include_gps:
                record.position_lat = start_lat + record_index * 0.00005
                record.position_long = start_lon + record_index * 0.00005

            # Power: exact value from interval
            record.power = power_w
            total_power_sum += power_w
            max_power = max(max_power, power_w)

            # HR: estimate based on power (roughly linear relationship)
            if include_hr:
                # Simple model: HR = 100 + (power / 3)
                hr = min(200, 100 + power_w // 3)
                record.heart_rate = hr
                max_hr = max(max_hr, hr)

            # Cadence: typical cycling cadence with slight variation
            if include_cadence:
                record.cadence = 85 + (record_index % 10)

            # Speed: ~30 km/h = 8.33 m/s with slight variation based on power
            speed = 7.0 + (power_w / 100)
            record.speed = speed

            # Distance: cumulative
            total_distance += speed
            record.distance = total_distance

            # Altitude: gentle climb
            record.altitude = 500.0 + (record_index * 0.1)

            builder.add(record)
            record_index += 1

    # Calculate summary stats
    total_records = record_index
    elapsed_s = float(total_records - 1) if total_records > 1 else 0.0
    avg_power = total_power_sum // total_records if total_records > 0 else 0
    avg_hr = 100 + avg_power // 3 if include_hr else 0
    end_ts_ms = base_ts_ms + (total_records - 1) * 1000

    # Lap message
    lap = LapMessage()
    lap.timestamp = end_ts_ms
    lap.start_time = base_ts_ms
    lap.total_distance = total_distance
    lap.total_elapsed_time = elapsed_s
    lap.total_moving_time = elapsed_s
    if include_hr:
        lap.avg_heart_rate = avg_hr
        lap.max_heart_rate = max_hr
    lap.avg_power = avg_power
    lap.max_power = max_power
    builder.add(lap)

    # Session message
    session = SessionMessage()
    session.timestamp = end_ts_ms
    session.start_time = base_ts_ms
    session.total_distance = total_distance
    session.total_elapsed_time = elapsed_s
    session.total_moving_time = elapsed_s
    session.total_timer_time = elapsed_s
    session.total_ascent = int(total_records * 0.1)
    session.avg_speed = total_distance / elapsed_s if elapsed_s > 0 else 0
    session.max_speed = 12.0
    if include_hr:
        session.avg_heart_rate = avg_hr
        session.max_heart_rate = max_hr
    session.avg_power = avg_power
    session.max_power = max_power
    builder.add(session)

    fit = builder.build()
    return fit.to_bytes()


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