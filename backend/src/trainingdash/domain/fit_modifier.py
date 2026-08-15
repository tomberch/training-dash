"""FIT file modifier for device type spoofing.

This module provides pure functions to modify FIT files before uploading to providers.
The primary use case is changing the device type to unlock device-specific features
on platforms like Garmin Connect.

Architecture:
- Read: garmin_fit_sdk (Decoder) - parses FIT bytes into message dicts
- Write: fit_tool (FitFileBuilder) - builds new FIT from messages

The modification process:
1. Parse original FIT file to extract all messages
2. Rebuild the FIT file using fit_tool
3. Replace file_id and device_info messages with spoofed device values
4. Copy all other messages (records, laps, sessions) unchanged
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from garmin_fit_sdk import Decoder, Profile, Stream


class FitModificationError(Exception):
    """Raised when FIT file modification fails."""

    pass


@dataclass
class FitModifications:
    """Modifications to apply to a FIT file before upload.

    Attributes:
        device_product_id: Garmin product ID (e.g., 4062 for Edge 840).
            If None, keeps the original device info.
        manufacturer_id: Manufacturer ID (default: 1 for Garmin).
    """

    device_product_id: int | None = None
    manufacturer_id: int = 1  # Garmin


def get_device_list() -> list[dict]:
    """Return list of available devices from garmin-fit-sdk Profile.

    Returns:
        List of dicts with 'id', 'name', and 'display_name' for each device.
    """
    devices = []
    garmin_products = Profile["types"].get("garmin_product", {})

    for product_id, name in garmin_products.items():
        if isinstance(name, str) and isinstance(product_id, int):
            # Create a display name by formatting the raw name
            display_name = name.replace("_", " ").title()
            devices.append(
                {
                    "id": product_id,
                    "name": name,
                    "display_name": display_name,
                }
            )

    # Sort by name for easier browsing
    return sorted(devices, key=lambda d: d["display_name"])


# FIT epoch offset: seconds from Unix epoch to FIT epoch (1989-12-31 00:00:00 UTC)
FIT_EPOCH_OFFSET_SECONDS = 631065600


def _fit_to_unix_ms(fit_timestamp: int) -> int:
    """Convert FIT timestamp (seconds since FIT epoch) to Unix milliseconds."""
    return (fit_timestamp + FIT_EPOCH_OFFSET_SECONDS) * 1000


def modify_fit(fit_bytes: bytes, modifications: FitModifications) -> bytes:
    """Apply modifications to a FIT file and return new FIT bytes.

    This is a pure function - it does not modify the input bytes.

    Args:
        fit_bytes: Original FIT file bytes
        modifications: Modifications to apply

    Returns:
        Modified FIT file as bytes

    Raises:
        FitModificationError: If the FIT file cannot be parsed or rebuilt
    """
    if modifications.device_product_id is None:
        # No modifications requested, return original
        return fit_bytes

    try:
        # Parse the original FIT file with scaled values but raw timestamps
        stream = Stream.from_byte_array(bytearray(fit_bytes))
        decoder = Decoder(stream)
        messages, errors = decoder.read(
            convert_datetimes_to_dates=False,  # Keep timestamps as FIT epoch seconds
            convert_types_to_strings=False,  # Keep enum values as ints
        )

        if errors:
            raise FitModificationError(f"FIT decode errors: {errors}")

        # Build new FIT file
        builder = FitFileBuilder()

        # Track if we've added device info
        device_info_added = False

        # Get file creation time from original file_id
        # garmin-fit-sdk returns FIT timestamp (seconds since 1989-12-31)
        # fit_tool expects Unix timestamp in MILLISECONDS
        file_time_created_fit = None
        for msg in messages.get("file_id_mesgs", []):
            file_time_created_fit = msg.get("time_created")
            break

        if file_time_created_fit is not None:
            file_time_created_ms = _fit_to_unix_ms(file_time_created_fit)
        else:
            file_time_created_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Add spoofed file_id message
        file_id = FileIdMessage()
        file_id.type = 4  # activity
        file_id.manufacturer = modifications.manufacturer_id
        file_id.product = modifications.device_product_id
        file_id.serial_number = 3413264489  # Arbitrary serial number
        file_id.time_created = file_time_created_ms
        builder.add(file_id)

        # Add spoofed device_info message
        device_info = DeviceInfoMessage()
        device_info.manufacturer = modifications.manufacturer_id
        device_info.product = modifications.device_product_id
        device_info.serial_number = 3413264489
        device_info.device_index = 0
        builder.add(device_info)
        device_info_added = True

        # Copy record messages
        for msg in messages.get("record_mesgs", []):
            record = RecordMessage()
            _copy_record_fields(msg, record)
            builder.add(record)

        # Copy lap messages
        for msg in messages.get("lap_mesgs", []):
            lap = LapMessage()
            _copy_lap_fields(msg, lap)
            builder.add(lap)

        # Copy session messages
        for msg in messages.get("session_mesgs", []):
            session = SessionMessage()
            _copy_session_fields(msg, session)
            builder.add(session)

        # Build and return
        fit_file = builder.build()
        return fit_file.to_bytes()

    except FitModificationError:
        raise
    except Exception as e:
        raise FitModificationError(f"Failed to modify FIT file: {e}") from e


def _semicircles_to_degrees(semicircles: int) -> float:
    """Convert FIT semicircles to degrees."""
    return semicircles * (180.0 / (2**31))


def _copy_record_fields(src: dict, dest: RecordMessage) -> None:
    """Copy fields from parsed record dict to RecordMessage.

    garmin-fit-sdk returns scaled values (meters, m/s, etc.) except position
    which is in semicircles. fit_tool expects degrees for position.
    """
    if "timestamp" in src and src["timestamp"] is not None:
        dest.timestamp = _fit_to_unix_ms(src["timestamp"])
    if "position_lat" in src and src["position_lat"] is not None:
        dest.position_lat = _semicircles_to_degrees(src["position_lat"])
    if "position_long" in src and src["position_long"] is not None:
        dest.position_long = _semicircles_to_degrees(src["position_long"])
    if "heart_rate" in src and src["heart_rate"] is not None:
        dest.heart_rate = src["heart_rate"]
    if "cadence" in src and src["cadence"] is not None:
        dest.cadence = src["cadence"]
    if "power" in src and src["power"] is not None:
        dest.power = src["power"]
    # Prefer enhanced_speed over speed (same value but higher precision)
    if "enhanced_speed" in src and src["enhanced_speed"] is not None:
        dest.speed = src["enhanced_speed"]
    elif "speed" in src and src["speed"] is not None:
        dest.speed = src["speed"]
    # Prefer enhanced_altitude over altitude
    if "enhanced_altitude" in src and src["enhanced_altitude"] is not None:
        dest.altitude = src["enhanced_altitude"]
    elif "altitude" in src and src["altitude"] is not None:
        dest.altitude = src["altitude"]
    if "distance" in src and src["distance"] is not None:
        dest.distance = src["distance"]


def _copy_lap_fields(src: dict, dest: LapMessage) -> None:
    """Copy fields from parsed lap dict to LapMessage."""
    if "timestamp" in src and src["timestamp"] is not None:
        dest.timestamp = _fit_to_unix_ms(src["timestamp"])
    if "start_time" in src and src["start_time"] is not None:
        dest.start_time = _fit_to_unix_ms(src["start_time"])
    if "total_elapsed_time" in src and src["total_elapsed_time"] is not None:
        dest.total_elapsed_time = src["total_elapsed_time"]
    if "total_timer_time" in src and src["total_timer_time"] is not None:
        dest.total_timer_time = src["total_timer_time"]
    if "total_distance" in src and src["total_distance"] is not None:
        dest.total_distance = src["total_distance"]
    if "total_moving_time" in src and src["total_moving_time"] is not None:
        dest.total_moving_time = src["total_moving_time"]
    if "avg_heart_rate" in src and src["avg_heart_rate"] is not None:
        dest.avg_heart_rate = src["avg_heart_rate"]
    if "max_heart_rate" in src and src["max_heart_rate"] is not None:
        dest.max_heart_rate = src["max_heart_rate"]
    if "avg_power" in src and src["avg_power"] is not None:
        dest.avg_power = src["avg_power"]
    if "max_power" in src and src["max_power"] is not None:
        dest.max_power = src["max_power"]


def _copy_session_fields(src: dict, dest: SessionMessage) -> None:
    """Copy fields from parsed session dict to SessionMessage."""
    if "timestamp" in src and src["timestamp"] is not None:
        dest.timestamp = _fit_to_unix_ms(src["timestamp"])
    if "start_time" in src and src["start_time"] is not None:
        dest.start_time = _fit_to_unix_ms(src["start_time"])
    if "total_elapsed_time" in src and src["total_elapsed_time"] is not None:
        dest.total_elapsed_time = src["total_elapsed_time"]
    if "total_timer_time" in src and src["total_timer_time"] is not None:
        dest.total_timer_time = src["total_timer_time"]
    if "total_distance" in src and src["total_distance"] is not None:
        dest.total_distance = src["total_distance"]
    if "total_moving_time" in src and src["total_moving_time"] is not None:
        dest.total_moving_time = src["total_moving_time"]
    if "total_ascent" in src and src["total_ascent"] is not None:
        dest.total_ascent = src["total_ascent"]
    if "avg_speed" in src and src["avg_speed"] is not None:
        dest.avg_speed = src["avg_speed"]
    if "max_speed" in src and src["max_speed"] is not None:
        dest.max_speed = src["max_speed"]
    if "avg_heart_rate" in src and src["avg_heart_rate"] is not None:
        dest.avg_heart_rate = src["avg_heart_rate"]
    if "max_heart_rate" in src and src["max_heart_rate"] is not None:
        dest.max_heart_rate = src["max_heart_rate"]
    if "avg_power" in src and src["avg_power"] is not None:
        dest.avg_power = src["avg_power"]
    if "max_power" in src and src["max_power"] is not None:
        dest.max_power = src["max_power"]
