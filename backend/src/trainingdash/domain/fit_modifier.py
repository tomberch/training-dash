"""FIT file modifier for device type spoofing.

This module provides pure functions to modify FIT files before uploading to providers.
The primary use case is changing the device type to unlock device-specific features
on platforms like Garmin Connect.

Architecture:
- Uses fit_tool to parse and serialize FIT files
- Modifies manufacturer/product fields in FileIdMessage and DeviceInfoMessage
- Preserves ALL other data exactly as-is (same file size, all messages intact)

This approach ensures no data loss - all messages, fields, and custom data are preserved.
"""

from dataclasses import dataclass

from fit_tool.fit_file import FitFile
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from garmin_fit_sdk import Profile


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


def modify_fit(fit_bytes: bytes, modifications: FitModifications) -> bytes:
    """Apply modifications to a FIT file and return new FIT bytes.

    Uses fit_tool to parse the FIT file, modify manufacturer/product fields
    in FileIdMessage and DeviceInfoMessage records, then serialize back.
    All other data is preserved exactly as-is.

    Args:
        fit_bytes: Original FIT file bytes
        modifications: Modifications to apply

    Returns:
        Modified FIT file as bytes (same size as original)

    Raises:
        FitModificationError: If the FIT file cannot be parsed or modified
    """
    if modifications.device_product_id is None:
        # No modifications requested, return original
        return fit_bytes

    try:
        # Parse the FIT file
        fit = FitFile.from_bytes(fit_bytes)

        # Modify manufacturer/product in FileIdMessage and DeviceInfoMessage records
        for record in fit.records:
            if not hasattr(record, "message"):
                continue

            msg = record.message
            if not isinstance(msg, (FileIdMessage, DeviceInfoMessage)):
                continue

            # Update manufacturer if present
            if hasattr(msg, "manufacturer") and msg.manufacturer is not None:
                msg.manufacturer = modifications.manufacturer_id

            # Update product if present
            if hasattr(msg, "product") and msg.product is not None:
                msg.product = modifications.device_product_id

        # Serialize back to bytes
        return fit.to_bytes()

    except Exception as e:
        raise FitModificationError(f"Failed to modify FIT file: {e}") from e
