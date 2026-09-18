"""Surgical FIT file writer that preserves unknown fields.

This module provides byte-level FIT modification that survives real-world files
containing unknown/developer fields that fit_tool loses on round-trip.

The approach:
1. Walk the FIT record structure without parsing field values
2. Track definition messages to know field layouts
3. Patch specific fields in-place (same size) or splice new bytes
4. Recompute the file CRC

This preserves ALL bytes except the fields we explicitly modify.

FIT binary format reference:
- Header: 12 or 14 bytes (size, protocol, profile, data_size, ".FIT", optional CRC)
- Data: sequence of definition and data messages
- CRC: 2 bytes at end (CRC-16 of header + data)

Record header byte:
- Bit 7: compressed timestamp (not supported here)
- Bit 6: 1 = definition, 0 = data
- Bit 5: developer fields present (definition only)
- Bits 0-3: local message type (0-15)

Definition message body:
- Reserved: 1 byte
- Architecture: 1 byte (0 = little-endian)
- Global message number: 2 bytes
- Number of fields: 1 byte
- Field definitions: 3 bytes each (field_num, size, base_type)
- If developer fields: dev_field_count + dev_field_defs

Data message body:
- Field values in definition order, sizes from definition
"""

import struct
from dataclasses import dataclass
from typing import NamedTuple

from fit_tool.utils.crc import crc16


class FitWriteError(Exception):
    """Raised when FIT file modification fails."""

    pass


# FIT global message numbers
MESG_FILE_ID = 0
MESG_SESSION = 18
MESG_DEVICE_INFO = 23

# Field numbers within messages
# file_id: manufacturer=1, product=2
# device_info: manufacturer=2, product=4
# session: total_calories=11
FIELD_FILE_ID_MANUFACTURER = 1
FIELD_FILE_ID_PRODUCT = 2
FIELD_DEVICE_INFO_MANUFACTURER = 2
FIELD_DEVICE_INFO_PRODUCT = 4
FIELD_SESSION_TOTAL_CALORIES = 11


class FieldDef(NamedTuple):
    """A field definition within a FIT definition message."""

    field_num: int
    size: int
    base_type: int


@dataclass
class MessageDef:
    """A FIT definition message's metadata."""

    global_id: int
    fields: list[FieldDef]
    dev_fields: list[FieldDef]
    total_data_size: int


@dataclass
class RecordInfo:
    """Information about a FIT record's location and type."""

    start: int  # byte offset in file
    end: int  # byte offset of first byte after this record
    is_definition: bool
    local_id: int
    global_id: int  # global message id (from definition for data records)
    msg_def: MessageDef | None  # definition that applies to this record (for data records)


def _parse_header(fit_bytes: bytes) -> tuple[int, int]:
    """Parse FIT header, return (header_size, data_size)."""
    if len(fit_bytes) < 12:
        raise FitWriteError("FIT file too short for header")

    header_size = fit_bytes[0]
    if header_size not in (12, 14):
        raise FitWriteError(f"Invalid FIT header size: {header_size}")

    data_size = struct.unpack("<I", fit_bytes[4:8])[0]

    # Verify ".FIT" signature
    if fit_bytes[8:12] != b".FIT":
        raise FitWriteError("Invalid FIT signature")

    # Verify file is large enough for declared data + CRC
    min_size = header_size + data_size + 2  # +2 for trailing CRC
    if len(fit_bytes) < min_size:
        raise FitWriteError(
            f"FIT file truncated: expected {min_size} bytes, got {len(fit_bytes)}"
        )

    return header_size, data_size


def walk_records(fit_bytes: bytes) -> list[RecordInfo]:
    """Walk FIT records without parsing field values.

    Returns list of RecordInfo for each record. Each data record includes
    the MessageDef that was active when it was encountered (FIT allows
    redefining local IDs mid-stream).
    """
    header_size, data_size = _parse_header(fit_bytes)

    records: list[RecordInfo] = []
    definitions: dict[int, MessageDef] = {}  # local_id -> current definition

    pos = header_size
    end_pos = header_size + data_size

    while pos < end_pos:
        start = pos
        header_byte = fit_bytes[pos]

        # Check for compressed timestamp header (bit 7 set)
        if header_byte & 0x80:
            # Compressed timestamp: local id in bits 5-6, timestamp offset in 0-4
            local_id = (header_byte >> 5) & 0x03
            pos += 1
            if local_id not in definitions:
                raise FitWriteError(
                    f"Data record for undefined local id {local_id} at offset {start}"
                )
            msg_def = definitions[local_id]
            pos += msg_def.total_data_size
            records.append(
                RecordInfo(
                    start=start,
                    end=pos,
                    is_definition=False,
                    local_id=local_id,
                    global_id=msg_def.global_id,
                    msg_def=msg_def,
                )
            )
            continue

        local_id = header_byte & 0x0F
        is_definition = bool(header_byte & 0x40)
        has_dev_fields = bool(header_byte & 0x20)
        pos += 1

        if is_definition:
            # Definition message
            if pos + 5 > end_pos:
                raise FitWriteError(f"Truncated definition at offset {start}")

            # reserved, architecture, global_id (2 bytes), num_fields
            arch = fit_bytes[pos + 1]
            if arch != 0:
                raise FitWriteError(
                    f"Big-endian FIT files not supported (offset {start})"
                )

            global_id = struct.unpack("<H", fit_bytes[pos + 2 : pos + 4])[0]
            num_fields = fit_bytes[pos + 4]
            pos += 5

            # Read field definitions
            fields: list[FieldDef] = []
            for _ in range(num_fields):
                if pos + 3 > end_pos:
                    raise FitWriteError(f"Truncated field definition at offset {pos}")
                field_num = fit_bytes[pos]
                field_size = fit_bytes[pos + 1]
                base_type = fit_bytes[pos + 2]
                fields.append(FieldDef(field_num, field_size, base_type))
                pos += 3

            # Developer fields (if present)
            dev_fields: list[FieldDef] = []
            if has_dev_fields:
                if pos >= end_pos:
                    raise FitWriteError(f"Truncated dev field count at offset {pos}")
                num_dev_fields = fit_bytes[pos]
                pos += 1
                for _ in range(num_dev_fields):
                    if pos + 3 > end_pos:
                        raise FitWriteError(f"Truncated dev field def at offset {pos}")
                    field_num = fit_bytes[pos]
                    field_size = fit_bytes[pos + 1]
                    dev_index = fit_bytes[pos + 2]
                    dev_fields.append(FieldDef(field_num, field_size, dev_index))
                    pos += 3

            total_data_size = sum(f.size for f in fields) + sum(
                f.size for f in dev_fields
            )
            msg_def = MessageDef(
                global_id=global_id,
                fields=fields,
                dev_fields=dev_fields,
                total_data_size=total_data_size,
            )
            definitions[local_id] = msg_def

            records.append(
                RecordInfo(
                    start=start,
                    end=pos,
                    is_definition=True,
                    local_id=local_id,
                    global_id=global_id,
                    msg_def=msg_def,
                )
            )

        else:
            # Data message
            if local_id not in definitions:
                raise FitWriteError(
                    f"Data record for undefined local id {local_id} at offset {start}"
                )
            msg_def = definitions[local_id]
            pos += msg_def.total_data_size

            records.append(
                RecordInfo(
                    start=start,
                    end=pos,
                    is_definition=False,
                    local_id=local_id,
                    global_id=msg_def.global_id,
                    msg_def=msg_def,
                )
            )

    return records


def _find_field_offset(
    record: RecordInfo,
    target_field_num: int,
) -> tuple[int, int] | None:
    """Find the byte offset and size of a field within a data record.

    Returns (offset, size) or None if the field is not in this message's definition.
    """
    if record.msg_def is None:
        return None

    # Data starts right after the 1-byte header
    data_start = record.start + 1

    offset = data_start
    for field in record.msg_def.fields:
        if field.field_num == target_field_num:
            return offset, field.size
        offset += field.size

    return None


def _recompute_crc(fit_bytes: bytes) -> bytes:
    """Recompute and update the trailing CRC."""
    # CRC covers everything except the last 2 bytes
    crc_value = crc16(fit_bytes[:-2])
    return fit_bytes[:-2] + struct.pack("<H", crc_value)


def spoof_device(
    fit_bytes: bytes,
    manufacturer_id: int,
    product_id: int,
) -> bytes:
    """Spoof the device manufacturer and product in a FIT file.

    Patches manufacturer and product fields in:
    - file_id message (global 0): fields 1 and 2
    - device_info messages (global 23): fields 2 and 4

    Args:
        fit_bytes: Original FIT file bytes
        manufacturer_id: New manufacturer ID (1 = Garmin)
        product_id: New product ID (e.g., 4062 = Edge 840)

    Returns:
        Modified FIT bytes with updated CRC

    Raises:
        FitWriteError: If the file cannot be parsed
    """
    records = walk_records(fit_bytes)
    result = bytearray(fit_bytes)

    for record in records:
        if record.is_definition:
            continue

        # Determine which fields to patch based on message type
        if record.global_id == MESG_FILE_ID:
            manufacturer_field = FIELD_FILE_ID_MANUFACTURER
            product_field = FIELD_FILE_ID_PRODUCT
        elif record.global_id == MESG_DEVICE_INFO:
            manufacturer_field = FIELD_DEVICE_INFO_MANUFACTURER
            product_field = FIELD_DEVICE_INFO_PRODUCT
        else:
            continue

        # Patch manufacturer if present
        mfr_loc = _find_field_offset(record, manufacturer_field)
        if mfr_loc:
            offset, size = mfr_loc
            if size == 2:
                struct.pack_into("<H", result, offset, manufacturer_id)

        # Patch product if present
        prod_loc = _find_field_offset(record, product_field)
        if prod_loc:
            offset, size = prod_loc
            if size == 2:
                struct.pack_into("<H", result, offset, product_id)

    return bytes(_recompute_crc(result))


def inject_session_calories(
    fit_bytes: bytes,
    calories: int,
    *,
    only_if_missing: bool = True,
) -> tuple[bytes, bool]:
    """Inject total_calories into the session message (best-effort).

    Args:
        fit_bytes: Original FIT file bytes
        calories: Calorie value to inject
        only_if_missing: If True, skip injection if the field already exists

    Returns:
        Tuple of (result_bytes, injected) where:
        - result_bytes: Modified FIT bytes if injection succeeded, original bytes otherwise
        - injected: True if calories were actually written, False if skipped/failed

    Note:
        This is a best-effort operation per spec #675. If the session message
        definition doesn't include total_calories (common in Karoo files),
        returns original bytes unchanged rather than failing the upload.
    """
    try:
        records = walk_records(fit_bytes)
    except FitWriteError:
        # Can't parse file structure — return original
        return fit_bytes, False

    result = bytearray(fit_bytes)
    patched = False

    for record in records:
        if record.is_definition or record.global_id != MESG_SESSION:
            continue

        field_loc = _find_field_offset(record, FIELD_SESSION_TOTAL_CALORIES)
        if field_loc is None:
            # Field not in definition — can't inject, return original (best-effort)
            continue

        offset, size = field_loc

        # Check current value if only_if_missing
        if only_if_missing:
            current = struct.unpack("<H", fit_bytes[offset : offset + size])[0]
            if current != 0xFFFF and current != 0:
                # Field has a value, skip
                continue

        if size != 2:
            # Unexpected field size — skip this record
            continue

        struct.pack_into("<H", result, offset, calories)
        patched = True

    if patched:
        return bytes(_recompute_crc(result)), True
    else:
        return fit_bytes, False
