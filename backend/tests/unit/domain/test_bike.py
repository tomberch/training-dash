"""Tests for bike domain logic (CdA/Crr defaults, validation)."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from trainingdash.domain.bike import (
    BIKE_TYPE_DEFAULTS,
    BIKE_TYPES,
    CALIBRATION_ELIGIBLE_BIKE_TYPES,
    get_effective_cda,
    get_effective_crr,
    is_calibration_eligible,
    validate_bike_type,
)


class TestBikeTypeConstants:
    """Tests for bike type constants."""

    def test_all_types_defined(self):
        """All expected bike types are in BIKE_TYPES."""
        expected = {"road", "tt", "gravel", "mtb", "ebike"}
        assert BIKE_TYPES == expected

    def test_calibration_eligible_subset(self):
        """Calibration eligible types are a subset of all types."""
        assert CALIBRATION_ELIGIBLE_BIKE_TYPES.issubset(BIKE_TYPES)

    def test_calibration_eligible_excludes_ebike(self):
        """Calibration eligible types exclude ebike."""
        expected = {"road", "tt", "gravel", "mtb"}
        assert CALIBRATION_ELIGIBLE_BIKE_TYPES == expected
        assert "ebike" not in CALIBRATION_ELIGIBLE_BIKE_TYPES

    def test_defaults_defined_for_all_types(self):
        """BIKE_TYPE_DEFAULTS has entries for all bike types."""
        for bike_type in BIKE_TYPES:
            assert bike_type in BIKE_TYPE_DEFAULTS
            assert "cda" in BIKE_TYPE_DEFAULTS[bike_type]
            assert "crr" in BIKE_TYPE_DEFAULTS[bike_type]

    def test_default_values_reasonable(self):
        """Default CdA and Crr values are within reasonable ranges."""
        for bike_type, defaults in BIKE_TYPE_DEFAULTS.items():
            # CdA typically 0.2-0.5 m² for cyclists
            assert 0.2 <= defaults["cda"] <= 0.5, f"{bike_type} CdA out of range"
            # Crr typically 0.002-0.015 for bike tires
            assert 0.002 <= defaults["crr"] <= 0.015, f"{bike_type} Crr out of range"

    def test_tt_has_lowest_cda(self):
        """TT bike has lowest CdA (most aero)."""
        tt_cda = BIKE_TYPE_DEFAULTS["tt"]["cda"]
        for bike_type, defaults in BIKE_TYPE_DEFAULTS.items():
            if bike_type != "tt":
                assert defaults["cda"] >= tt_cda

    def test_mtb_has_highest_crr(self):
        """MTB has highest Crr (knobby tires)."""
        mtb_crr = BIKE_TYPE_DEFAULTS["mtb"]["crr"]
        for bike_type, defaults in BIKE_TYPE_DEFAULTS.items():
            if bike_type != "mtb":
                assert defaults["crr"] <= mtb_crr


class TestGetEffectiveCda:
    """Tests for get_effective_cda function."""

    def _make_bike(self, bike_type: str, cda: float | None = None) -> MagicMock:
        """Create a mock bike with given attributes."""
        bike = MagicMock()
        bike.bike_type = bike_type
        bike.cda = Decimal(str(cda)) if cda is not None else None
        return bike

    def test_returns_bike_cda_when_set(self):
        """Returns the bike's CdA if explicitly set."""
        bike = self._make_bike("road", cda=0.28)
        assert get_effective_cda(bike) == 0.28

    def test_returns_default_when_cda_none(self):
        """Returns default CdA for bike type when not set."""
        for bike_type in BIKE_TYPES:
            bike = self._make_bike(bike_type, cda=None)
            expected = BIKE_TYPE_DEFAULTS[bike_type]["cda"]
            assert get_effective_cda(bike) == expected

    def test_returns_float(self):
        """Always returns a float, even if bike.cda is Decimal."""
        bike = self._make_bike("road", cda=0.30)
        result = get_effective_cda(bike)
        assert isinstance(result, float)


class TestGetEffectiveCrr:
    """Tests for get_effective_crr function."""

    def _make_bike(self, bike_type: str, crr: float | None = None) -> MagicMock:
        """Create a mock bike with given attributes."""
        bike = MagicMock()
        bike.bike_type = bike_type
        bike.crr = Decimal(str(crr)) if crr is not None else None
        return bike

    def test_returns_bike_crr_when_set(self):
        """Returns the bike's Crr if explicitly set."""
        bike = self._make_bike("road", crr=0.0035)
        assert get_effective_crr(bike) == 0.0035

    def test_returns_default_when_crr_none(self):
        """Returns default Crr for bike type when not set."""
        for bike_type in BIKE_TYPES:
            bike = self._make_bike(bike_type, crr=None)
            expected = BIKE_TYPE_DEFAULTS[bike_type]["crr"]
            assert get_effective_crr(bike) == expected

    def test_returns_float(self):
        """Always returns a float, even if bike.crr is Decimal."""
        bike = self._make_bike("road", crr=0.004)
        result = get_effective_crr(bike)
        assert isinstance(result, float)


class TestIsCalibrationEligible:
    """Tests for is_calibration_eligible function."""

    def _make_bike(self, bike_type: str) -> MagicMock:
        """Create a mock bike with given bike_type."""
        bike = MagicMock()
        bike.bike_type = bike_type
        return bike

    def test_road_eligible(self):
        """Road bikes are eligible for calibration."""
        assert is_calibration_eligible(self._make_bike("road")) is True

    def test_tt_eligible(self):
        """TT bikes are eligible for calibration."""
        assert is_calibration_eligible(self._make_bike("tt")) is True

    def test_gravel_eligible(self):
        """Gravel bikes are eligible for calibration."""
        assert is_calibration_eligible(self._make_bike("gravel")) is True

    def test_mtb_eligible(self):
        """MTB bikes are eligible for calibration."""
        assert is_calibration_eligible(self._make_bike("mtb")) is True

    def test_ebike_not_eligible(self):
        """E-bikes are not eligible (motor skews power data)."""
        assert is_calibration_eligible(self._make_bike("ebike")) is False


class TestValidateBikeType:
    """Tests for validate_bike_type function."""

    def test_valid_types_return_true(self):
        """Valid bike types return True."""
        for bike_type in BIKE_TYPES:
            assert validate_bike_type(bike_type) is True

    def test_invalid_type_returns_false(self):
        """Invalid bike types return False."""
        assert validate_bike_type("invalid") is False
        assert validate_bike_type("bike") is False
        assert validate_bike_type("") is False
        assert validate_bike_type("ROAD") is False  # Case-sensitive

    def test_activity_types_not_valid_bike_types(self):
        """Activity types that aren't bike types return False."""
        assert validate_bike_type("virtual") is False
        assert validate_bike_type("indoor") is False
        assert validate_bike_type("commute") is False
        assert validate_bike_type("other") is False
