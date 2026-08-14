"""Tests for the field registry."""

import pytest

from trainingdash.domain.query.fields import (
    FIELD_ALIASES,
    FIELD_DEFINITIONS,
    FieldType,
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
