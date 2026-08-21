"""Tests for bike domain logic (CdA/Crr defaults, validation)."""

from decimal import Decimal

from trainingdash.domain.bike import (
    BIKE_TYPE_DEFAULTS,
    BIKE_TYPES,
    CALIBRATION_ELIGIBLE_BIKE_TYPES,
    get_effective_cda,
    get_effective_crr,
    is_calibration_eligible_type,
    validate_bike_type,
)


class TestBikeTypeConstants:
    """Tests for bike type constants."""

    def test_all_types_defined(self):
        """All expected bike types are in BIKE_TYPES."""
        expected = {"road", "tt", "gravel", "mtb", "ebike"}
        assert expected == BIKE_TYPES

    def test_calibration_eligible_subset(self):
        """Calibration eligible types are a subset of all types."""
        assert CALIBRATION_ELIGIBLE_BIKE_TYPES.issubset(BIKE_TYPES)

    def test_calibration_eligible_excludes_ebike(self):
        """Calibration eligible types exclude ebike."""
        expected = {"road", "tt", "gravel", "mtb"}
        assert expected == CALIBRATION_ELIGIBLE_BIKE_TYPES
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

    def test_returns_cda_when_set(self):
        """Returns the provided CdA if explicitly set."""
        assert get_effective_cda("road", 0.28) == 0.28

    def test_returns_cda_from_decimal(self):
        """Returns float when CdA is a Decimal."""
        result = get_effective_cda("road", Decimal("0.30"))
        assert result == 0.30
        assert isinstance(result, float)

    def test_returns_default_when_cda_none(self):
        """Returns default CdA for bike type when not set."""
        for bike_type in BIKE_TYPES:
            expected = BIKE_TYPE_DEFAULTS[bike_type]["cda"]
            assert get_effective_cda(bike_type, None) == expected


class TestGetEffectiveCrr:
    """Tests for get_effective_crr function."""

    def test_returns_crr_when_set(self):
        """Returns the provided Crr if explicitly set."""
        assert get_effective_crr("road", 0.0035) == 0.0035

    def test_returns_crr_from_decimal(self):
        """Returns float when Crr is a Decimal."""
        result = get_effective_crr("road", Decimal("0.004"))
        assert result == 0.004
        assert isinstance(result, float)

    def test_returns_default_when_crr_none(self):
        """Returns default Crr for bike type when not set."""
        for bike_type in BIKE_TYPES:
            expected = BIKE_TYPE_DEFAULTS[bike_type]["crr"]
            assert get_effective_crr(bike_type, None) == expected


class TestIsCalibrationEligibleType:
    """Tests for is_calibration_eligible_type function."""

    def test_road_eligible(self):
        """Road bikes are eligible for calibration."""
        assert is_calibration_eligible_type("road") is True

    def test_tt_eligible(self):
        """TT bikes are eligible for calibration."""
        assert is_calibration_eligible_type("tt") is True

    def test_gravel_eligible(self):
        """Gravel bikes are eligible for calibration."""
        assert is_calibration_eligible_type("gravel") is True

    def test_mtb_eligible(self):
        """MTB bikes are eligible for calibration."""
        assert is_calibration_eligible_type("mtb") is True

    def test_ebike_not_eligible(self):
        """E-bikes are not eligible (motor skews power data)."""
        assert is_calibration_eligible_type("ebike") is False


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
