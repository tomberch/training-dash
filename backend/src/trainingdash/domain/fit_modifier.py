"""FIT file modifier for device type spoofing.

This module provides pure functions to modify FIT files before uploading to providers.
The primary use case is changing the device type to unlock device-specific features
on platforms like Garmin Connect.

Architecture:
- Uses surgical byte-patching via fit_writer module
- Walks FIT record structure, patches manufacturer/product fields in-place
- Preserves ALL other data exactly as-is (unknown fields, developer data, everything)
- Recomputes CRC after modification

This approach survives real-world FIT files that fit_tool cannot round-trip (files with
unknown fields, developer data, etc. cause fit_tool to skip data and produce CRC mismatches).
"""

from dataclasses import dataclass

from garmin_fit_sdk import Profile

from trainingdash.domain.fit_writer import FitWriteError, spoof_device


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

    Uses surgical byte-patching to modify manufacturer/product fields
    in file_id and device_info messages. All other data is preserved
    exactly as-is, including unknown fields and developer data.

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
        return spoof_device(
            fit_bytes,
            manufacturer_id=modifications.manufacturer_id,
            product_id=modifications.device_product_id,
        )
    except FitWriteError as e:
        raise FitModificationError(f"Failed to modify FIT file: {e}") from e
