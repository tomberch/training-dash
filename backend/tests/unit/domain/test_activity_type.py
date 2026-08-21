"""Tests for activity type detection from FIT sport/sub_sport fields."""

import pytest

from trainingdash.domain.activity_type import (
    ACTIVITY_TYPES,
    CALIBRATION_ELIGIBLE_TYPES,
    detect_activity_type,
    is_calibration_eligible,
    validate_activity_type,
)


class TestDetectActivityType:
    """Tests for detect_activity_type function."""

    def test_virtual_activity(self):
        """Virtual activity sub_sport maps to virtual."""
        assert detect_activity_type("cycling", "virtual_activity") == "virtual"
        assert detect_activity_type("cycling", "virtual") == "virtual"

    def test_indoor_cycling(self):
        """Indoor cycling sub_sport maps to indoor."""
        assert detect_activity_type("cycling", "indoor_cycling") == "indoor"
        assert detect_activity_type("cycling", "indoor") == "indoor"

    def test_mountain_biking(self):
        """Mountain biking sub_sport maps to mtb."""
        assert detect_activity_type("cycling", "mountain") == "mtb"
        assert detect_activity_type("cycling", "mtb") == "mtb"
        assert detect_activity_type("cycling", "mountain_biking") == "mtb"

    def test_gravel_cycling(self):
        """Gravel/cyclocross sub_sport maps to gravel."""
        assert detect_activity_type("cycling", "gravel_cycling") == "gravel"
        assert detect_activity_type("cycling", "gravel") == "gravel"
        assert detect_activity_type("cycling", "cyclocross") == "gravel"
        assert detect_activity_type("cycling", "cx") == "gravel"

    def test_commute(self):
        """Commute/transportation sub_sport maps to commute."""
        assert detect_activity_type("cycling", "commuting") == "commute"
        assert detect_activity_type("cycling", "cycling_transportation") == "commute"
        assert detect_activity_type("cycling", "commute") == "commute"
        assert detect_activity_type("cycling", "transport") == "commute"

    def test_road_cycling(self):
        """Road cycling sub_sport maps to road."""
        assert detect_activity_type("cycling", "road") == "road"

    def test_generic_cycling_defaults_to_road(self):
        """Generic or missing sub_sport defaults to road."""
        assert detect_activity_type("cycling", "generic") == "road"
        assert detect_activity_type("cycling", "") == "road"
        assert detect_activity_type("cycling", None) == "road"

    def test_unknown_sub_sport_defaults_to_road(self):
        """Unknown sub_sport defaults to road."""
        assert detect_activity_type("cycling", "unknown_type") == "road"

    def test_ebike_detection(self):
        """E-bike activity types map to ebike."""
        # Sport field detection
        assert detect_activity_type("e_biking", None) == "ebike"
        assert detect_activity_type("e_biking", "road") == "ebike"
        # Sub_sport field detection
        assert detect_activity_type("cycling", "e_biking") == "ebike"
        assert detect_activity_type("cycling", "ebike") == "ebike"
        assert detect_activity_type("cycling", "e_bike") == "ebike"
        assert detect_activity_type("cycling", "electric") == "ebike"

    def test_non_cycling_sport_returns_other(self):
        """Non-cycling sports return other."""
        assert detect_activity_type("running", "trail") == "other"
        assert detect_activity_type("swimming", "open_water") == "other"
        assert detect_activity_type("hiking", None) == "other"

    def test_missing_sport_defaults_to_road(self):
        """Missing sport with cycling sub_sport defaults to road."""
        # If sport is missing but we're processing a FIT file, assume cycling
        assert detect_activity_type(None, "road") == "road"
        assert detect_activity_type("", "generic") == "road"

    def test_case_insensitive(self):
        """Detection is case-insensitive."""
        assert detect_activity_type("CYCLING", "VIRTUAL_ACTIVITY") == "virtual"
        assert detect_activity_type("Cycling", "Indoor_Cycling") == "indoor"
        assert detect_activity_type("cycling", "Mountain") == "mtb"

    def test_whitespace_handling(self):
        """Detection handles whitespace in values."""
        assert detect_activity_type(" cycling ", " virtual_activity ") == "virtual"


class TestIsCalibrationEligible:
    """Tests for is_calibration_eligible function."""

    def test_outdoor_types_eligible(self):
        """Outdoor activity types are eligible."""
        assert is_calibration_eligible("road") is True
        assert is_calibration_eligible("gravel") is True
        assert is_calibration_eligible("mtb") is True
        assert is_calibration_eligible("commute") is True

    def test_indoor_types_not_eligible(self):
        """Indoor activity types are not eligible."""
        assert is_calibration_eligible("virtual") is False
        assert is_calibration_eligible("indoor") is False

    def test_ebike_not_eligible(self):
        """E-bike types are not eligible for calibration."""
        assert is_calibration_eligible("ebike") is False

    def test_other_not_eligible(self):
        """Other/unknown types are not eligible."""
        assert is_calibration_eligible("other") is False

    def test_null_not_eligible(self):
        """Null (unclassified) is not eligible."""
        assert is_calibration_eligible(None) is False

    def test_invalid_type_not_eligible(self):
        """Invalid types are not eligible."""
        assert is_calibration_eligible("invalid") is False
        assert is_calibration_eligible("") is False


class TestActivityTypeConstants:
    """Tests for activity type constants."""

    def test_all_types_defined(self):
        """All expected activity types are in ACTIVITY_TYPES."""
        expected = {"road", "gravel", "mtb", "virtual", "indoor", "commute", "ebike", "other"}
        assert expected == ACTIVITY_TYPES

    def test_calibration_eligible_subset(self):
        """Calibration eligible types are a subset of all types."""
        assert CALIBRATION_ELIGIBLE_TYPES.issubset(ACTIVITY_TYPES)

    def test_calibration_eligible_types(self):
        """Calibration eligible types are the outdoor ones."""
        expected = {"road", "gravel", "mtb", "commute"}
        assert expected == CALIBRATION_ELIGIBLE_TYPES


class TestValidateActivityType:
    """Tests for validate_activity_type function."""

    def test_valid_types_pass(self):
        """Valid activity types are returned as-is."""
        assert validate_activity_type("road") == "road"
        assert validate_activity_type("gravel") == "gravel"
        assert validate_activity_type("mtb") == "mtb"
        assert validate_activity_type("virtual") == "virtual"
        assert validate_activity_type("indoor") == "indoor"
        assert validate_activity_type("commute") == "commute"
        assert validate_activity_type("ebike") == "ebike"
        assert validate_activity_type("other") == "other"

    def test_empty_string_returns_none(self):
        """Empty string returns None (unclassified)."""
        assert validate_activity_type("") is None

    def test_invalid_type_raises(self):
        """Invalid activity type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid activity_type"):
            validate_activity_type("invalid")
        with pytest.raises(ValueError, match="Invalid activity_type"):
            validate_activity_type("bike")
        with pytest.raises(ValueError, match="Invalid activity_type"):
            validate_activity_type("ROAD")  # Case-sensitive
