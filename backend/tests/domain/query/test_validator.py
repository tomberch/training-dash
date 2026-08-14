"""Tests for the query validator."""

from datetime import datetime

import pytest

from trainingdash.domain.query import (
    NumberValue,
    DateValue,
    StringValue,
    BoolValue,
    Comparison,
    Between,
    InList,
    TextMatch,
    BooleanField,
    parse,
    validate,
    ValidationError,
)


class TestFieldAliasResolution:
    """Test that field aliases are resolved to internal names."""

    def test_distance_alias(self):
        query = parse("distance > 50km")
        validated = validate(query)
        assert validated.conditions.field == "total_distance_m"

    def test_elevation_alias(self):
        query = parse("elevation > 1000m")
        validated = validate(query)
        assert validated.conditions.field == "elevation_gain_m"

    def test_duration_alias(self):
        query = parse("duration > 1:00:00")
        validated = validate(query)
        assert validated.conditions.field == "moving_time_s"

    def test_power_alias(self):
        query = parse("power > 200")
        validated = validate(query)
        assert validated.conditions.field == "avg_power_w"

    def test_np_alias(self):
        query = parse("np > 250")
        validated = validate(query)
        assert validated.conditions.field == "np_power_w"

    def test_date_alias(self):
        query = parse("date >= 2026-01-01")
        validated = validate(query)
        assert validated.conditions.field == "started_at"

    def test_hr_alias(self):
        query = parse("hr > 150")
        validated = validate(query)
        assert validated.conditions.field == "avg_hr_bpm"

    def test_breakthrough_alias(self):
        query = parse("breakthrough = true")
        validated = validate(query)
        assert validated.conditions.field == "is_breakthrough"

    def test_internal_name_preserved(self):
        query = parse("total_distance_m > 50000")
        validated = validate(query)
        assert validated.conditions.field == "total_distance_m"


class TestUnknownFieldErrors:
    """Test error messages for unknown fields."""

    def test_unknown_field_error(self):
        query = parse("unknown_field > 100")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Unknown field" in exc.value.message
        assert exc.value.field == "unknown_field"

    def test_typo_suggestion(self):
        query = parse("tsss > 100")  # Typo: extra 's'
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert exc.value.field == "tsss"
        assert "tss" in exc.value.suggestions

    def test_distance_typo_suggestion(self):
        query = parse("distanc > 50km")  # Missing 'e'
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "distance" in exc.value.suggestions

    def test_error_str_includes_suggestions(self):
        query = parse("tsss > 100")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        error_str = str(exc.value)
        assert "Did you mean" in error_str


class TestUnitConversion:
    """Test that units are converted to internal units."""

    def test_km_to_m(self):
        query = parse("distance > 50km")
        validated = validate(query)
        value = validated.conditions.value
        assert isinstance(value, NumberValue)
        assert value.value == 50000.0  # 50 km = 50000 m
        assert value.unit is None  # Unit removed after conversion

    def test_mi_to_m(self):
        query = parse("distance > 10mi")
        validated = validate(query)
        value = validated.conditions.value
        assert value.value == pytest.approx(16093.44)

    def test_kph_to_mps(self):
        query = parse("speed > 30kph")
        validated = validate(query)
        value = validated.conditions.value
        assert value.value == pytest.approx(8.333, rel=0.01)  # 30 kph ≈ 8.33 m/s

    def test_hours_to_seconds(self):
        query = parse("duration > 2h")
        validated = validate(query)
        value = validated.conditions.value
        assert value.value == 7200.0  # 2h = 7200s

    def test_minutes_to_seconds(self):
        query = parse("duration > 90min")
        validated = validate(query)
        value = validated.conditions.value
        assert value.value == 5400.0  # 90min = 5400s

    def test_no_unit_no_conversion(self):
        query = parse("tss > 100")
        validated = validate(query)
        value = validated.conditions.value
        assert value.value == 100.0
        assert value.unit is None

    def test_colon_duration_to_seconds(self):
        query = parse("duration > 1:30:00")
        validated = validate(query)
        value = validated.conditions.value
        assert value.value == 5400.0  # 1h30m = 5400s


class TestRelativeDateResolution:
    """Test that relative dates are resolved to absolute datetimes."""

    def test_now(self):
        query = parse("date >= NOW")
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        value = validated.conditions.value
        assert isinstance(value, DateValue)
        assert value.value == now

    def test_today(self):
        query = parse("date >= TODAY")
        now = datetime(2026, 8, 14, 12, 30, 45)
        validated = validate(query, now=now)
        value = validated.conditions.value
        assert value.value == datetime(2026, 8, 14, 0, 0, 0)

    def test_start_of_week(self):
        query = parse("date >= START_OF_WEEK")
        # August 14, 2026 is a Friday (weekday=4)
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        value = validated.conditions.value
        # Monday was August 10
        assert value.value == datetime(2026, 8, 10, 0, 0, 0)

    def test_start_of_month(self):
        query = parse("date >= START_OF_MONTH")
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        value = validated.conditions.value
        assert value.value == datetime(2026, 8, 1, 0, 0, 0)

    def test_start_of_year(self):
        query = parse("date >= START_OF_YEAR")
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        value = validated.conditions.value
        assert value.value == datetime(2026, 1, 1, 0, 0, 0)

    def test_now_minus_days(self):
        query = parse("date >= NOW - 30d")
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        value = validated.conditions.value
        assert value.value == datetime(2026, 7, 15, 12, 0, 0)

    def test_now_plus_days(self):
        query = parse("date <= NOW + 7d")
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        value = validated.conditions.value
        assert value.value == datetime(2026, 8, 21, 12, 0, 0)


class TestTypeMismatchErrors:
    """Test error handling for type mismatches."""

    def test_string_on_number_field(self):
        query = parse('tss = "high"')
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "String value not valid" in exc.value.message

    def test_number_on_string_field(self):
        query = parse("title > 100")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Operator '>' is not valid" in exc.value.message

    def test_date_on_number_field(self):
        query = parse("tss > 2026-01-01")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Date value not valid" in exc.value.message

    def test_text_match_on_number_field(self):
        query = parse('tss CONTAINS "100"')
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Text matching" in exc.value.message

    def test_boolean_standalone_on_non_boolean(self):
        query = parse("tss")  # tss is not boolean
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "not a boolean field" in exc.value.message


class TestOperatorValidation:
    """Test operator compatibility validation."""

    def test_gt_on_number(self):
        query = parse("tss > 100")
        validated = validate(query)  # Should not raise
        assert validated.conditions.op == ">"

    def test_gt_on_string_fails(self):
        query = parse('source > "xert"')
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Operator '>' is not valid" in exc.value.message

    def test_eq_on_string(self):
        query = parse('source = "xert"')
        validated = validate(query)  # Should not raise
        assert validated.conditions.op == "="


class TestBetweenValidation:
    """Test BETWEEN expression validation."""

    def test_between_numbers(self):
        query = parse("tss BETWEEN 50 AND 100")
        validated = validate(query)
        assert isinstance(validated.conditions, Between)
        assert validated.conditions.field == "tss"

    def test_between_with_units(self):
        query = parse("distance BETWEEN 50km AND 100km")
        validated = validate(query)
        assert validated.conditions.low.value == 50000.0
        assert validated.conditions.high.value == 100000.0

    def test_between_dates(self):
        query = parse("date BETWEEN 2026-01-01 AND 2026-06-30")
        validated = validate(query)
        assert isinstance(validated.conditions.low, DateValue)

    def test_between_on_string_fails(self):
        query = parse('source BETWEEN "a" AND "z"')
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "BETWEEN is not valid" in exc.value.message


class TestInListValidation:
    """Test IN expression validation."""

    def test_in_strings(self):
        query = parse('source IN ("xert", "garmin")')
        validated = validate(query)
        assert isinstance(validated.conditions, InList)
        assert validated.conditions.field == "source"

    def test_in_numbers(self):
        query = parse("tss IN (100, 150, 200)")
        validated = validate(query)
        assert len(validated.conditions.values) == 3

    def test_not_in(self):
        query = parse('source NOT IN ("upload")')
        validated = validate(query)
        assert validated.conditions.negated is True


class TestNullCheckValidation:
    """Test IS NULL / IS NOT NULL validation."""

    def test_nullable_field_is_null(self):
        query = parse("power IS NULL")
        validated = validate(query)
        assert validated.conditions.field == "avg_power_w"
        assert validated.conditions.is_null is True

    def test_nullable_field_is_not_null(self):
        query = parse("power IS NOT NULL")
        validated = validate(query)
        assert validated.conditions.is_null is False

    def test_non_nullable_is_null_fails(self):
        query = parse("source IS NULL")  # source is never NULL
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "never NULL" in exc.value.message


class TestTextMatchValidation:
    """Test text matching validation."""

    def test_contains_on_string(self):
        query = parse('title CONTAINS "recovery"')
        validated = validate(query)
        assert isinstance(validated.conditions, TextMatch)
        assert validated.conditions.field == "title"

    def test_starts_with_on_string(self):
        query = parse('title STARTS WITH "Morning"')
        validated = validate(query)
        assert validated.conditions.op == "STARTS_WITH"

    def test_contains_on_number_fails(self):
        query = parse('tss CONTAINS "100"')
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Text matching" in exc.value.message


class TestBooleanFieldValidation:
    """Test standalone boolean field validation."""

    def test_boolean_field_standalone(self):
        query = parse("breakthrough")
        validated = validate(query)
        assert isinstance(validated.conditions, BooleanField)
        assert validated.conditions.field == "is_breakthrough"


class TestProjectionValidation:
    """Test SELECT projection validation."""

    def test_select_fields(self):
        query = parse("SELECT tss, distance, elevation WHERE tss > 100")
        validated = validate(query)
        assert validated.projection.fields == ["tss", "total_distance_m", "elevation_gain_m"]

    def test_select_unknown_field(self):
        query = parse("SELECT tss, unknown_field WHERE tss > 100")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Unknown field" in exc.value.message


class TestOrderByValidation:
    """Test ORDER BY validation."""

    def test_order_by_alias(self):
        query = parse("tss > 100 ORDER BY elevation DESC")
        validated = validate(query)
        assert validated.order_by[0].field == "elevation_gain_m"

    def test_order_by_unknown_field(self):
        query = parse("tss > 100 ORDER BY unknown_field DESC")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Unknown field" in exc.value.message


class TestGroupByValidation:
    """Test GROUP BY validation."""

    def test_group_by_time_bucket(self):
        query = parse("COUNT(*) GROUP BY month")
        validated = validate(query)
        assert validated.group_by[0].kind == "time_bucket"
        assert validated.group_by[0].value == "month"

    def test_group_by_field(self):
        query = parse("COUNT(*) GROUP BY source")
        validated = validate(query)
        assert validated.group_by[0].kind == "field"
        assert validated.group_by[0].value == "source"

    def test_group_by_unknown_field(self):
        query = parse("COUNT(*) GROUP BY unknown_field")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "Unknown field" in exc.value.message


class TestAggregationValidation:
    """Test aggregation expression validation."""

    def test_count_star(self):
        query = parse("COUNT(*)")
        validated = validate(query)
        assert validated.projection.aggregates[0].func == "COUNT"
        assert validated.projection.aggregates[0].field is None

    def test_avg_on_numeric_field(self):
        query = parse("AVG(tss)")
        validated = validate(query)
        assert validated.projection.aggregates[0].field == "tss"

    def test_sum_with_alias(self):
        query = parse("SUM(distance)")
        validated = validate(query)
        assert validated.projection.aggregates[0].field == "total_distance_m"

    def test_avg_on_string_fails(self):
        query = parse("AVG(title)")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "cannot be used" in exc.value.message

    def test_sum_star_fails(self):
        query = parse("SUM(*)")
        with pytest.raises(ValidationError) as exc:
            validate(query)
        assert "SUM(*) is not valid" in exc.value.message


class TestComplexQueryValidation:
    """Test validation of complex queries."""

    def test_full_query(self):
        query = parse(
            'SELECT summary WHERE tss > 100 AND source IN ("xert", "garmin") '
            "ORDER BY date DESC LIMIT 20"
        )
        validated = validate(query)
        assert validated.type == "list"
        assert validated.projection.kind == "view"
        assert validated.conditions is not None
        assert validated.order_by is not None
        assert validated.limit == 20

    def test_aggregation_with_group_and_filter(self):
        query = parse(
            "COUNT(*), AVG(tss), SUM(distance) WHERE date >= START_OF_YEAR GROUP BY month"
        )
        now = datetime(2026, 8, 14)
        validated = validate(query, now=now)
        assert validated.type == "aggregate"
        assert len(validated.projection.aggregates) == 3
        assert validated.conditions is not None
        assert validated.group_by is not None
