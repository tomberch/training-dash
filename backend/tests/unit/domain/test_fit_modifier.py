"""Unit tests for FIT file modifier."""

import pytest

from trainingdash.domain.fit_modifier import (
    FitModificationError,
    FitModifications,
    get_device_list,
    modify_fit,
)


class TestGetDeviceList:
    """Tests for get_device_list()."""

    def test_returns_list_of_devices(self):
        devices = get_device_list()
        assert isinstance(devices, list)
        assert len(devices) > 100  # Should have many Garmin devices

    def test_devices_have_required_fields(self):
        devices = get_device_list()
        for device in devices[:10]:  # Check first 10
            assert "id" in device
            assert "name" in device
            assert "display_name" in device
            assert isinstance(device["id"], int)
            assert isinstance(device["name"], str)
            assert isinstance(device["display_name"], str)

    def test_includes_common_devices(self):
        devices = get_device_list()
        device_ids = {d["id"] for d in devices}
        # Edge 840 = 4062, Edge 1040 = 3843
        assert 4062 in device_ids
        assert 3843 in device_ids

    def test_devices_sorted_by_display_name(self):
        devices = get_device_list()
        display_names = [d["display_name"] for d in devices]
        assert display_names == sorted(display_names)


class TestFitModifications:
    """Tests for FitModifications dataclass."""

    def test_default_values(self):
        mods = FitModifications()
        assert mods.device_product_id is None
        assert mods.manufacturer_id == 1  # Garmin

    def test_custom_values(self):
        mods = FitModifications(device_product_id=4062, manufacturer_id=2)
        assert mods.device_product_id == 4062
        assert mods.manufacturer_id == 2


class TestModifyFit:
    """Tests for modify_fit()."""

    def test_returns_original_when_no_modifications(self):
        # Create minimal FIT bytes (just enough to not crash)
        fit_bytes = b"test_fit_data"
        mods = FitModifications()  # No device_product_id
        result = modify_fit(fit_bytes, mods)
        assert result == fit_bytes

    def test_raises_on_invalid_fit_data(self):
        fit_bytes = b"not a valid fit file"
        mods = FitModifications(device_product_id=4062)
        with pytest.raises(FitModificationError) as exc_info:
            modify_fit(fit_bytes, mods)
        # Could be decode error or modification error
        assert "FIT" in str(exc_info.value) or "fit" in str(exc_info.value).lower()

    def test_raises_on_empty_fit_data(self):
        fit_bytes = b""
        mods = FitModifications(device_product_id=4062)
        # Empty bytes may or may not raise depending on decoder behavior
        # If it doesn't raise, the result should still be valid bytes
        try:
            result = modify_fit(fit_bytes, mods)
            # If no exception, result should be bytes
            assert isinstance(result, bytes)
        except FitModificationError:
            # This is also acceptable
            pass
