"""
Generate synthesized FIT fixtures for the calories feature (#670).

Two message shapes, ground-truthed against real files (since deleted for
privacy — this repo is public) during the original bug analysis:

1. `garmin_style_activity.fit` — session message WITH total_calories
   (+ per-lap total_calories), Garmin manufacturer/product, HR-based ride
   (no power records). Mirrors a Garmin device export where the device
   computed calories on-board (Firstbeat).

2. `karoo_style_activity.fit` — session message WITHOUT total_calories,
   record messages with power + HR, an unknown DeviceInfo field (field id
   32, as written by Hammerhead Karoo), developer_data_id +
   field_description messages, and event messages with fields the fit_tool
   profile doesn't define (19/20). Mirrors a Karoo export downloaded from
   Xert. This file reproduces the fit_tool round-trip failure (CRC
   mismatch in `modify_fit`) that the research ticket (#671) must solve.

Both decode cleanly with garmin_fit_sdk (the decoder used by
ingest.parse_records).

Run directly to (re)generate the checked-in fixture files:

    uv run python tests/fixtures/generate_calories_fixtures.py

The generated files live in backend/tests/fixtures/calories/.
"""

import struct
from pathlib import Path

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.utils.crc import crc16 as _crc16

# NOTE: run directly (python tests/fixtures/generate_calories_fixtures.py) from the
# repo root so that the sibling generate_fit module resolves when imported.

# Fixed parameters so fixtures are reproducible byte-for-byte.
START_TS_MS = 1710506400000  # 2024-03-15 12:40:00 UTC
N_RECORDS = 60
POWER_W = 200
HR_BPM = 150
KNOWN_CALORIES = 238  # device-reported value in the Garmin-style session

# FIT file timestamps are seconds since 1989-12-31 UTC (not unix epoch).
FIT_EPOCH_OFFSET_S = 631065600  # seconds between 1970-01-01 and 1989-12-31

FIXTURES_DIR = (
    Path(__file__).parent.parent.parent / "backend" / "tests" / "fixtures" / "calories"
)

# ---------------------------------------------------------------------------
# FIT binary primitives (for the surgical unknown-field extension)
# ---------------------------------------------------------------------------


def _definition_header(local_id: int) -> bytes:
    """Definition record header: bit 6 set, local message type in bits 0-3."""
    return bytes([0x40 | local_id])


def _data_header(local_id: int) -> bytes:
    """Data record header: bit 6 clear, local message type in bits 0-3."""
    return bytes([local_id])


def _definition_message(
    local_id: int, global_id: int, fields: list[tuple[int, int, int]]
) -> bytes:
    """Build a FIT definition message.

    fields: list of (field_number, size_in_bytes, base_type_code).
    """
    # Definition message body: reserved(1) + arch(1) + global_id(2) + num_fields(1)
    body = struct.pack("<BBHB", 0, 0, global_id, len(fields))
    for field_num, size, base_type in fields:
        body += struct.pack("<BBB", field_num, size, base_type)
    return _definition_header(local_id) + body


def _data_message(local_id: int, payload: bytes) -> bytes:
    """Build a FIT data message with the given local id and raw payload."""
    return _data_header(local_id) + payload


def _walk_records(fit_bytes: bytes) -> list[tuple[int, int, int]]:
    """Walk FIT records. Returns list of (start, end, global_id_or_None) for
    each record. Definition records report their global id."""
    results: list[tuple[int, int, int]] = []
    definitions: dict[int, int] = {}  # local_id -> global message id
    sizes: dict[int, int] = {}  # local_id -> data message size
    pos = 12
    end = 12 + struct.unpack("<I", fit_bytes[4:8])[0]
    while pos < end:
        start = pos
        header_byte = fit_bytes[pos]
        local_id = header_byte & 0x0F
        is_definition = bool(header_byte & 0x40)
        pos += 1
        if is_definition:
            # Definition body: reserved(1), arch(1), global_id(2 LE), num_fields(1)
            arch = fit_bytes[pos + 1]
            if arch != 0:
                raise ValueError("Only little-endian FIT supported")
            global_id = struct.unpack("<H", fit_bytes[pos + 2 : pos + 4])[0]
            num_fields = fit_bytes[pos + 4]
            msg_size = sum(fit_bytes[pos + 5 + i * 3 + 1] for i in range(num_fields))
            definitions[local_id] = global_id
            sizes[local_id] = msg_size
            pos += 5 + num_fields * 3
        else:
            msg_size = sizes[local_id]
            pos += msg_size
        results.append((start, pos, definitions.get(local_id)))
    return results


def _inject_after_global_id(
    fit_bytes: bytes, after_global_id: int, new_messages: bytes
) -> bytes:
    """Splice new raw messages after the last record with the given global id."""
    records = _walk_records(fit_bytes)
    insert_at = None
    for start, end_pos, global_id in records:
        if global_id == after_global_id:
            insert_at = end_pos
    if insert_at is None:
        raise ValueError(f"No record with global id {after_global_id} found")

    body_without_crc = fit_bytes[:-2]
    new_body = (
        body_without_crc[:insert_at] + new_messages + body_without_crc[insert_at:]
    )

    # Update header data size
    new_data_size = len(new_body) - 12
    new_body = bytearray(new_body)
    struct.pack_into("<I", new_body, 4, new_data_size)

    crc = _crc16(bytes(new_body))
    return bytes(new_body) + struct.pack("<H", crc)


# ---------------------------------------------------------------------------
# Garmin-style fixture
# ---------------------------------------------------------------------------


def make_garmin_style_fit() -> bytes:
    """Session WITH total_calories (device Firstbeat-style), laps with
    per-lap calories, HR-only ride (no power records)."""
    builder = FitFileBuilder()

    file_id = FileIdMessage()
    file_id.type = 4  # activity
    file_id.time_created = START_TS_MS
    builder.add(file_id)

    # Garmin Edge 530, garmin manufacturer id 1, product 3121
    device_info = DeviceInfoMessage()
    device_info.manufacturer = 1
    device_info.product = 3121
    builder.add(device_info)

    lap_calories = [KNOWN_CALORIES // 2, KNOWN_CALORIES - KNOWN_CALORIES // 2]
    records_per_lap = N_RECORDS // 2

    for lap_index in range(2):
        lap = LapMessage()
        lap.timestamp = START_TS_MS + (lap_index + 1) * records_per_lap * 1000
        lap.start_time = START_TS_MS + lap_index * records_per_lap * 1000
        lap.total_calories = lap_calories[lap_index]
        builder.add(lap)

    for i in range(N_RECORDS):
        record = RecordMessage()
        record.timestamp = START_TS_MS + i * 1000
        record.heart_rate = HR_BPM
        record.distance = 7.0 * i  # 25 km/h
        record.speed = 6.944  # 25 km/h in m/s
        builder.add(record)

    session = SessionMessage()
    session.timestamp = START_TS_MS + N_RECORDS * 1000
    session.start_time = START_TS_MS
    session.total_elapsed_time = float(N_RECORDS)
    session.total_timer_time = float(N_RECORDS)
    session.total_distance = 7.0 * N_RECORDS
    session.total_calories = KNOWN_CALORIES  # device-computed calories
    session.avg_heart_rate = HR_BPM
    session.max_heart_rate = HR_BPM
    session.sport = 2  # cycling
    builder.add(session)

    return builder.build().to_bytes()


# ---------------------------------------------------------------------------
# Karoo-style fixture
# ---------------------------------------------------------------------------


def make_karoo_style_fit() -> bytes:
    """Session WITHOUT total_calories, power + HR records, unknown
    DeviceInfo field 32, developer_data_id + field_definition messages,
    event fields 19/20.

    Base file built with fit_tool (standard messages), then extended
    byte-surgically with the messages fit_tool can't express — the same
    surgical property the production rewrite module needs.
    """
    builder = FitFileBuilder()

    file_id = FileIdMessage()
    file_id.type = 4
    file_id.time_created = START_TS_MS
    builder.add(file_id)

    # Karoo: Hammerhead manufacturer 29281 (0x7261), product 3
    device_info = DeviceInfoMessage()
    device_info.manufacturer = 29281
    device_info.product = 3
    builder.add(device_info)

    # Session WITHOUT total_calories, but WITH power stats — Karoo computes
    # NP/IF/TSS on-device (observed in the real file).
    session = SessionMessage()
    session.timestamp = START_TS_MS + N_RECORDS * 1000
    session.start_time = START_TS_MS
    session.total_elapsed_time = float(N_RECORDS)
    session.total_timer_time = float(N_RECORDS)
    session.avg_power = POWER_W
    session.max_power = 400
    session.normalized_power = 210
    session.avg_heart_rate = HR_BPM
    session.sport = 2  # cycling
    builder.add(session)

    lap = LapMessage()
    lap.timestamp = START_TS_MS + N_RECORDS * 1000
    lap.start_time = START_TS_MS
    lap.total_elapsed_time = float(N_RECORDS)
    lap.avg_power = POWER_W
    builder.add(lap)

    for i in range(N_RECORDS):
        record = RecordMessage()
        record.timestamp = START_TS_MS + i * 1000
        record.heart_rate = HR_BPM
        record.power = POWER_W
        record.distance = 7.0 * i
        record.speed = 6.944
        builder.add(record)

    base = builder.build().to_bytes()

    # ---- Byte-surgical extension: messages fit_tool cannot express ----

    # Local ids chosen to avoid collision with fit_tool's allocation
    # (fit_tool allocates local ids per distinct message type; the base file
    # here uses local ids 0..3. We use 4..7 with fresh definitions.)
    unknown_device_info_fields = _definition_message(
        local_id=4,
        global_id=23,  # device_info
        fields=[
            # field number 4 (manufacturer), size 2, uint16 — duplicate the
            # known field so the message decodes; the unknown-field case is
            # covered by the *record* definition below with truly unknown ids.
            (4, 2, 0x84),
            # Karoo's unknown field 32: not in the SDK profile (the SDK logs
            # "Field id: 32 is not defined for message device_info").
            (32, 4, 0x86),
        ],
    ) + _data_message(local_id=4, payload=struct.pack("<HI", 29281, 0xDEADBEEF))

    # Record definition with unknown fields 107/134-138/143 (Karoo record
    # fields the SDK skips) — a second record definition with local id 5.
    unknown_record_fields = _definition_message(
        local_id=5,
        global_id=20,  # record
        fields=[
            (253, 4, 0x86),  # timestamp (known, required for ordering)
            (107, 1, 0x02),  # unknown Karoo field
            (143, 1, 0x02),  # unknown Karoo field
        ],
    ) + _data_message(
        local_id=5,
        payload=struct.pack(
            "<IBB",
            (START_TS_MS + N_RECORDS * 1000 + 1000) // 1000 - FIT_EPOCH_OFFSET_S,
            0x55,
            0xAA,
        ),
    )

    # Event message with fields 19/20 (not in the SDK event profile)
    event_with_unknown_fields = _definition_message(
        local_id=6,
        global_id=21,  # event
        fields=[
            (253, 4, 0x86),  # timestamp
            (0, 1, 0x00),  # event (enum, 1 byte)
            (1, 1, 0x00),  # event_type (enum, 1 byte)
            (19, 2, 0x84),  # unknown field
            (20, 2, 0x84),  # unknown field
        ],
    ) + _data_message(
        local_id=6,
        payload=struct.pack(
            "<IBBHH",
            (START_TS_MS + N_RECORDS * 1000 + 2000) // 1000 - FIT_EPOCH_OFFSET_S,
            42,
            4,
            0x0101,
            0x0202,
        ),
    )

    # Developer data id (global 207) + field description (global 206) —
    # Karoo writes developer fields; the SDK reads them but fit_tool loses them.
    developer_data_id = _definition_message(
        local_id=7,
        global_id=207,  # developer_data_id
        fields=[
            (253, 4, 0x86),  # timestamp
            (0, 16, 0x0A),  # developer_id (byte array)
            (3, 1, 0x02),  # developer_data_index (uint8)
        ],
    ) + _data_message(
        local_id=7,
        payload=struct.pack("<I", START_TS_MS // 1000 - FIT_EPOCH_OFFSET_S)
        + bytes(range(16))
        + struct.pack("<B", 1),
    )

    field_description = _definition_message(
        local_id=7,
        global_id=206,  # field_description
        fields=[
            (253, 4, 0x86),  # timestamp
            (0, 1, 0x02),  # developer_data_index (uint8)
            (1, 1, 0x02),  # field_definition_number (uint8)
            (2, 1, 0x00),  # fit_base_type_id (enum → uint8)
            (3, 8, 0x00),  # field_name (string, array)
        ],
    ) + _data_message(
        local_id=7,
        payload=struct.pack(
            "<IBBBB", START_TS_MS // 1000 - FIT_EPOCH_OFFSET_S, 1, 99, 2, 0
        )
        + b"charge\x00",
    )

    # Splice: unknown device_info after the file_id's records area — insert
    # all extension messages right after the last record message (global 20).
    extension = (
        unknown_device_info_fields
        + unknown_record_fields
        + event_with_unknown_fields
        + developer_data_id
        + field_description
    )
    return _inject_after_global_id(base, 20, extension)


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    garmin_fit = make_garmin_style_fit()
    (FIXTURES_DIR / "garmin_style_activity.fit").write_bytes(garmin_fit)
    print(
        f"Wrote {FIXTURES_DIR / 'garmin_style_activity.fit'} ({len(garmin_fit)} bytes)"
    )

    karoo_fit = make_karoo_style_fit()
    (FIXTURES_DIR / "karoo_style_activity.fit").write_bytes(karoo_fit)
    print(f"Wrote {FIXTURES_DIR / 'karoo_style_activity.fit'} ({len(karoo_fit)} bytes)")


if __name__ == "__main__":
    main()
