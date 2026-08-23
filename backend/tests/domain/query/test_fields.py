"""Tests for the field registry."""

import pytest

from trainingdash.domain.query.fields import (
    FIELD_ALIASES,
    FIELD_DEFINITIONS,
    FieldType,
    convert_temperature,
    get_conversion_factor,
    get_field_def,
    is_aggregatable,
    is_text_match_valid,
    is_valid_operator,
    resolve_field_name,
    suggest_field_name,
)


class TestResolveFieldName:
    """Test field name resolution."""

    def test_internal_name_exact(self):
        assert resolve_field_name("total_distance_m") == "total_distance_m"

    def test_internal_name_case_insensitive(self):
        assert resolve_field_name("Total_Distance_M") == "total_distance_m"
        assert resolve_field_name("TSS") == "tss"

    def test_alias_to_internal(self):
        assert resolve_field_name("distance") == "total_distance_m"
        assert resolve_field_name("elevation") == "elevation_gain_m"
        assert resolve_field_name("duration") == "moving_time_s"
        assert resolve_field_name("power") == "avg_power_w"
        assert resolve_field_name("np") == "np_power_w"
        assert resolve_field_name("date") == "started_at"

    def test_new_field_aliases(self):
        """Test newly added field aliases."""
        # Activity type
        assert resolve_field_name("type") == "activity_type"
        assert resolve_field_name("activity") == "activity_type"
        # Bike
        assert resolve_field_name("bike") == "bike_id"
        # Cadence
        assert resolve_field_name("cadence") == "avg_cadence_rpm"
        assert resolve_field_name("rpm") == "avg_cadence_rpm"
        assert resolve_field_name("max_cadence") == "max_cadence_rpm"
        # Temperature
        assert resolve_field_name("temp") == "avg_temperature_c"
        assert resolve_field_name("temperature") == "avg_temperature_c"
        assert resolve_field_name("min_temp") == "min_temperature_c"
        assert resolve_field_name("max_temp") == "max_temperature_c"
        # Max power
        assert resolve_field_name("max_power") == "max_power_w"
        # Elevation loss
        assert resolve_field_name("descent") == "elevation_loss_m"
        # Grade
        assert resolve_field_name("grade") == "max_grade_pct"
        assert resolve_field_name("gradient") == "max_grade_pct"
        # Aero
        assert resolve_field_name("cda") == "estimated_cda"
        assert resolve_field_name("crr") == "estimated_crr"

    def test_zone_time_aliases(self):
        """Test power and HR zone time aliases."""
        # Power zones
        assert resolve_field_name("pz1") == "power_zone_1_s"
        assert resolve_field_name("pz5") == "power_zone_5_s"
        assert resolve_field_name("pz7") == "power_zone_7_s"
        assert resolve_field_name("power_z3") == "power_zone_3_s"
        # HR zones
        assert resolve_field_name("hz1") == "hr_zone_1_s"
        assert resolve_field_name("hz5") == "hr_zone_5_s"
        assert resolve_field_name("hr_z3") == "hr_zone_3_s"

    def test_alias_case_insensitive(self):
        assert resolve_field_name("Distance") == "total_distance_m"
        assert resolve_field_name("POWER") == "avg_power_w"

    def test_unknown_field_returns_none(self):
        assert resolve_field_name("unknown_field") is None
        assert resolve_field_name("tsss") is None  # Typo

    def test_all_aliases_resolve(self):
        """Verify all aliases point to valid internal names."""
        for alias, internal in FIELD_ALIASES.items():
            assert internal in FIELD_DEFINITIONS, f"Alias '{alias}' -> '{internal}' not in definitions"


class TestGetFieldDef:
    """Test field definition retrieval."""

    def test_get_by_internal_name(self):
        field_def = get_field_def("total_distance_m")
        assert field_def is not None
        assert field_def.internal_name == "total_distance_m"
        assert field_def.field_type == FieldType.NUMBER
        assert field_def.internal_unit == "m"

    def test_get_by_alias(self):
        field_def = get_field_def("distance")
        assert field_def is not None
        assert field_def.internal_name == "total_distance_m"

    def test_get_unknown_returns_none(self):
        assert get_field_def("unknown") is None

    def test_boolean_field(self):
        field_def = get_field_def("is_breakthrough")
        assert field_def.field_type == FieldType.BOOLEAN
        assert field_def.nullable is False

    def test_nullable_field(self):
        field_def = get_field_def("avg_power_w")
        assert field_def.nullable is True

    def test_non_nullable_field(self):
        field_def = get_field_def("started_at")
        assert field_def.nullable is False

    def test_new_field_definitions(self):
        """Test newly added field definitions."""
        # Activity type
        field_def = get_field_def("activity_type")
        assert field_def.field_type == FieldType.STRING
        assert field_def.nullable is True

        # Bike ID
        field_def = get_field_def("bike_id")
        assert field_def.field_type == FieldType.NUMBER
        assert field_def.nullable is True

        # Cadence
        field_def = get_field_def("avg_cadence_rpm")
        assert field_def.field_type == FieldType.NUMBER
        assert field_def.nullable is True

        # Max power
        field_def = get_field_def("max_power_w")
        assert field_def.field_type == FieldType.NUMBER
        assert field_def.nullable is True

        # Temperature
        field_def = get_field_def("avg_temperature_c")
        assert field_def.field_type == FieldType.NUMBER
        assert field_def.internal_unit == "c"
        assert field_def.nullable is True

    def test_zone_time_field_definitions(self):
        """Test zone time field definitions are marked as computed."""
        # Power zones
        field_def = get_field_def("power_zone_5_s")
        assert field_def.field_type == FieldType.DURATION
        assert field_def.internal_unit == "s"
        assert field_def.computed is True
        assert field_def.nullable is True

        # HR zones
        field_def = get_field_def("hr_zone_3_s")
        assert field_def.field_type == FieldType.DURATION
        assert field_def.internal_unit == "s"
        assert field_def.computed is True


class TestSuggestFieldName:
    """Test field name suggestions for typos."""

    def test_simple_typo(self):
        suggestions = suggest_field_name("distanc")  # Missing 'e'
        assert "distance" in suggestions

    def test_double_letter_typo(self):
        suggestions = suggest_field_name("tsss")  # Extra 's'
        assert "tss" in suggestions

    def test_case_typo(self):
        suggestions = suggest_field_name("Tss")
        assert "tss" in suggestions

    def test_completely_wrong_returns_empty(self):
        suggestions = suggest_field_name("xyzabc123")
        assert len(suggestions) == 0

    def test_max_suggestions(self):
        suggestions = suggest_field_name("tim", max_suggestions=2)
        assert len(suggestions) <= 2

    def test_prefers_aliases(self):
        # "dist" should suggest "distance" not "total_distance_m"
        suggestions = suggest_field_name("dist")
        if suggestions:
            assert suggestions[0] in ("distance", "dist")


class TestUnitConversion:
    """Test unit conversion factors."""

    def test_km_to_m(self):
        factor = get_conversion_factor("km", "m")
        assert factor == 1000.0

    def test_mi_to_m(self):
        factor = get_conversion_factor("mi", "m")
        assert factor == pytest.approx(1609.344)

    def test_ft_to_m(self):
        factor = get_conversion_factor("ft", "m")
        assert factor == pytest.approx(0.3048)

    def test_kph_to_mps(self):
        factor = get_conversion_factor("kph", "mps")
        assert factor == pytest.approx(1 / 3.6)

    def test_mph_to_mps(self):
        factor = get_conversion_factor("mph", "mps")
        assert factor == pytest.approx(0.44704)

    def test_h_to_s(self):
        factor = get_conversion_factor("h", "s")
        assert factor == 3600.0

    def test_min_to_s(self):
        factor = get_conversion_factor("min", "s")
        assert factor == 60.0

    def test_same_unit(self):
        assert get_conversion_factor("m", "m") == 1.0
        assert get_conversion_factor("s", "s") == 1.0

    def test_case_insensitive(self):
        assert get_conversion_factor("KM", "m") == 1000.0
        assert get_conversion_factor("km", "M") == 1000.0

    def test_unsupported_conversion(self):
        assert get_conversion_factor("km", "s") is None  # distance to time
        assert get_conversion_factor("unknown", "m") is None


class TestTemperatureConversion:
    """Test temperature unit conversion."""

    def test_fahrenheit_to_celsius_freezing(self):
        assert convert_temperature(32, "f") == 0.0

    def test_fahrenheit_to_celsius_room_temp(self):
        assert convert_temperature(68, "f") == 20.0

    def test_fahrenheit_to_celsius_body_temp(self):
        assert convert_temperature(98.6, "f") == pytest.approx(37.0, rel=0.01)

    def test_fahrenheit_to_celsius_boiling(self):
        assert convert_temperature(212, "f") == 100.0

    def test_celsius_unchanged(self):
        assert convert_temperature(20, "c") == 20
        assert convert_temperature(0, "c") == 0

    def test_case_insensitive(self):
        assert convert_temperature(68, "F") == 20.0
        assert convert_temperature(20, "C") == 20

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError) as exc:
            convert_temperature(20, "k")
        assert "Unknown temperature unit" in str(exc.value)


class TestOperatorValidation:
    """Test operator/type compatibility."""

    def test_number_operators(self):
        assert is_valid_operator(FieldType.NUMBER, "=")
        assert is_valid_operator(FieldType.NUMBER, "!=")
        assert is_valid_operator(FieldType.NUMBER, ">")
        assert is_valid_operator(FieldType.NUMBER, ">=")
        assert is_valid_operator(FieldType.NUMBER, "<")
        assert is_valid_operator(FieldType.NUMBER, "<=")

    def test_string_operators(self):
        assert is_valid_operator(FieldType.STRING, "=")
        assert is_valid_operator(FieldType.STRING, "!=")
        assert not is_valid_operator(FieldType.STRING, ">")
        assert not is_valid_operator(FieldType.STRING, "<")

    def test_date_operators(self):
        assert is_valid_operator(FieldType.DATE, "=")
        assert is_valid_operator(FieldType.DATE, ">=")
        assert is_valid_operator(FieldType.DATE, "<")

    def test_boolean_operators(self):
        assert is_valid_operator(FieldType.BOOLEAN, "=")
        assert is_valid_operator(FieldType.BOOLEAN, "!=")
        assert not is_valid_operator(FieldType.BOOLEAN, ">")

    def test_duration_operators(self):
        assert is_valid_operator(FieldType.DURATION, ">")
        assert is_valid_operator(FieldType.DURATION, "<=")


class TestTextMatchValidation:
    """Test text match operator validation."""

    def test_string_allows_text_match(self):
        assert is_text_match_valid(FieldType.STRING)

    def test_number_disallows_text_match(self):
        assert not is_text_match_valid(FieldType.NUMBER)

    def test_date_disallows_text_match(self):
        assert not is_text_match_valid(FieldType.DATE)


class TestAggregatable:
    """Test aggregatable field checks."""

    def test_numeric_fields_aggregatable(self):
        assert is_aggregatable("tss")
        assert is_aggregatable("total_distance_m")
        assert is_aggregatable("avg_power_w")

    def test_alias_aggregatable(self):
        assert is_aggregatable("distance")
        assert is_aggregatable("power")

    def test_string_not_aggregatable(self):
        assert not is_aggregatable("title")
        assert not is_aggregatable("source")

    def test_date_not_aggregatable(self):
        assert not is_aggregatable("started_at")

    def test_boolean_not_aggregatable(self):
        assert not is_aggregatable("is_breakthrough")

    def test_new_fields_aggregatable(self):
        """Test newly added fields are aggregatable."""
        # Cadence
        assert is_aggregatable("avg_cadence_rpm")
        assert is_aggregatable("max_cadence_rpm")
        assert is_aggregatable("cadence")  # alias
        # Temperature
        assert is_aggregatable("avg_temperature_c")
        assert is_aggregatable("min_temperature_c")
        assert is_aggregatable("max_temperature_c")
        assert is_aggregatable("temp")  # alias
        # Max power
        assert is_aggregatable("max_power_w")
        assert is_aggregatable("max_power")  # alias
        # Elevation loss
        assert is_aggregatable("elevation_loss_m")
        assert is_aggregatable("descent")  # alias
        # Grade
        assert is_aggregatable("max_grade_pct")
        # Aero
        assert is_aggregatable("estimated_cda")
        assert is_aggregatable("estimated_crr")

    def test_zone_time_fields_aggregatable(self):
        """Test zone time fields are aggregatable."""
        # Power zones
        assert is_aggregatable("power_zone_1_s")
        assert is_aggregatable("power_zone_5_s")
        assert is_aggregatable("power_zone_7_s")
        assert is_aggregatable("pz3")  # alias
        # HR zones
        assert is_aggregatable("hr_zone_1_s")
        assert is_aggregatable("hr_zone_5_s")
        assert is_aggregatable("hz3")  # alias

    def test_activity_type_not_aggregatable(self):
        """Test string fields are not aggregatable."""
        assert not is_aggregatable("activity_type")
        assert not is_aggregatable("type")  # alias
