"""Tests for the query DSL parser."""

from datetime import datetime

import pytest

from trainingdash.domain.query import (
    AggExpr,
    Between,
    BinaryOp,
    BooleanField,
    BoolValue,
    Comparison,
    DateValue,
    DurationValue,
    GroupKey,
    InList,
    NotOp,
    NullCheck,
    NumberValue,
    OrderItem,
    ParseError,
    RelativeDate,
    StringValue,
    TextMatch,
    parse,
)


class TestSimpleComparisons:
    """Test basic comparison expressions."""

    def test_simple_greater_than(self):
        result = parse("tss > 100")
        assert result.type == "list"
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.field == "tss"
        assert result.conditions.op == ">"
        assert result.conditions.value == NumberValue(value=100.0, unit=None)

    def test_greater_than_equal(self):
        result = parse("tss >= 100")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.op == ">="

    def test_less_than(self):
        result = parse("tss < 50")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.op == "<"

    def test_less_than_equal(self):
        result = parse("tss <= 50")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.op == "<="

    def test_equals(self):
        result = parse("source = \"xert\"")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.op == "="
        assert result.conditions.value == StringValue(value="xert")

    def test_not_equals(self):
        result = parse("source != \"upload\"")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.op == "!="


class TestNumbersWithUnits:
    """Test number literals with unit suffixes."""

    def test_distance_km(self):
        result = parse("distance > 50km")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=50.0, unit="km")

    def test_distance_mi(self):
        result = parse("distance > 30mi")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=30.0, unit="mi")

    def test_elevation_m(self):
        result = parse("elevation > 1000m")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=1000.0, unit="m")

    def test_elevation_ft(self):
        result = parse("elevation > 3000ft")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=3000.0, unit="ft")

    def test_speed_kph(self):
        result = parse("speed > 30kph")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=30.0, unit="kph")

    def test_speed_mph(self):
        result = parse("speed > 20mph")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=20.0, unit="mph")

    def test_duration_hours(self):
        result = parse("duration > 2h")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=2.0, unit="h")

    def test_duration_minutes(self):
        result = parse("duration > 90min")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=90.0, unit="min")

    def test_duration_seconds(self):
        result = parse("duration > 3600s")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=3600.0, unit="s")

    def test_decimal_with_unit(self):
        result = parse("distance > 42.195km")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == NumberValue(value=42.195, unit="km")

    def test_unit_case_insensitive(self):
        result = parse("distance > 50KM")
        assert result.conditions.value == NumberValue(value=50.0, unit="km")


class TestDurationColonFormat:
    """Test duration values in colon format."""

    def test_hours_minutes_seconds(self):
        result = parse("duration > 1:30:00")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == DurationValue(seconds=5400)

    def test_minutes_seconds(self):
        result = parse("duration > 45:30")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == DurationValue(seconds=2730)


class TestStringLiterals:
    """Test string literal parsing."""

    def test_double_quoted(self):
        result = parse('title CONTAINS "recovery"')
        assert isinstance(result.conditions, TextMatch)
        assert result.conditions.value == "recovery"

    def test_single_quoted(self):
        result = parse("title CONTAINS 'recovery'")
        assert isinstance(result.conditions, TextMatch)
        assert result.conditions.value == "recovery"

    def test_string_with_spaces(self):
        result = parse('title CONTAINS "morning ride"')
        assert isinstance(result.conditions, TextMatch)
        assert result.conditions.value == "morning ride"


class TestDateLiterals:
    """Test date and datetime parsing."""

    def test_date_only(self):
        result = parse("date >= 2026-01-01")
        assert isinstance(result.conditions, Comparison)
        assert isinstance(result.conditions.value, DateValue)
        assert result.conditions.value.value == datetime(2026, 1, 1, 0, 0, 0)

    def test_date_with_time(self):
        result = parse("date >= 2026-01-15T08:30:00")
        assert isinstance(result.conditions, Comparison)
        assert isinstance(result.conditions.value, DateValue)
        assert result.conditions.value.value == datetime(2026, 1, 15, 8, 30, 0)


class TestRelativeDates:
    """Test relative date expressions."""

    def test_now(self):
        result = parse("date >= NOW")
        assert isinstance(result.conditions, Comparison)
        assert isinstance(result.conditions.value, RelativeDate)
        assert result.conditions.value.base == "NOW"
        assert result.conditions.value.offset_days is None

    def test_today(self):
        result = parse("date >= TODAY")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.base == "TODAY"

    def test_start_of_week(self):
        result = parse("date >= START_OF_WEEK")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.base == "START_OF_WEEK"

    def test_start_of_month(self):
        result = parse("date >= START_OF_MONTH")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.base == "START_OF_MONTH"

    def test_start_of_year(self):
        result = parse("date >= START_OF_YEAR")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.base == "START_OF_YEAR"

    def test_now_minus_days(self):
        result = parse("date >= NOW - 30d")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.base == "NOW"
        assert result.conditions.value.offset_days == -30

    def test_now_plus_days(self):
        result = parse("date <= NOW + 7d")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.base == "NOW"
        assert result.conditions.value.offset_days == 7

    def test_now_minus_weeks(self):
        result = parse("date >= NOW - 2w")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.offset_days == -14

    def test_now_minus_months(self):
        result = parse("date >= NOW - 6mo")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.offset_days == -180  # 6 * 30

    def test_now_minus_years(self):
        result = parse("date >= NOW - 1y")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value.offset_days == -365

    def test_case_insensitive(self):
        result = parse("date >= now - 30D")
        assert result.conditions.value.base == "NOW"


class TestBooleanValues:
    """Test boolean literal parsing."""

    def test_true_value(self):
        result = parse("breakthrough = true")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == BoolValue(value=True)

    def test_false_value(self):
        result = parse("breakthrough = false")
        assert isinstance(result.conditions, Comparison)
        assert result.conditions.value == BoolValue(value=False)

    def test_case_insensitive(self):
        result = parse("breakthrough = TRUE")
        assert result.conditions.value == BoolValue(value=True)

    def test_boolean_field_standalone(self):
        result = parse("breakthrough")
        assert isinstance(result.conditions, BooleanField)
        assert result.conditions.field == "breakthrough"


class TestLogicalOperators:
    """Test AND, OR, NOT operators."""

    def test_and(self):
        result = parse("tss > 100 AND distance > 50km")
        assert isinstance(result.conditions, BinaryOp)
        assert result.conditions.op == "AND"
        assert isinstance(result.conditions.left, Comparison)
        assert isinstance(result.conditions.right, Comparison)

    def test_or(self):
        result = parse("tss > 100 OR breakthrough = true")
        assert isinstance(result.conditions, BinaryOp)
        assert result.conditions.op == "OR"

    def test_not(self):
        result = parse("NOT breakthrough = true")
        assert isinstance(result.conditions, NotOp)
        assert isinstance(result.conditions.expr, Comparison)

    def test_precedence_and_before_or(self):
        # A AND B OR C should be (A AND B) OR C
        result = parse("tss > 100 AND distance > 50km OR breakthrough = true")
        assert isinstance(result.conditions, BinaryOp)
        assert result.conditions.op == "OR"
        assert isinstance(result.conditions.left, BinaryOp)
        assert result.conditions.left.op == "AND"

    def test_parentheses_override_precedence(self):
        result = parse("tss > 100 AND (distance > 50km OR breakthrough = true)")
        assert isinstance(result.conditions, BinaryOp)
        assert result.conditions.op == "AND"
        assert isinstance(result.conditions.right, BinaryOp)
        assert result.conditions.right.op == "OR"

    def test_multiple_and(self):
        result = parse("tss > 100 AND distance > 50km AND elevation > 1000m")
        assert isinstance(result.conditions, BinaryOp)
        # Should be left-associative: ((A AND B) AND C)
        assert result.conditions.op == "AND"
        assert isinstance(result.conditions.left, BinaryOp)

    def test_case_insensitive(self):
        result = parse("tss > 100 and distance > 50km")
        assert isinstance(result.conditions, BinaryOp)
        assert result.conditions.op == "AND"


class TestBetweenOperator:
    """Test BETWEEN expressions."""

    def test_between_numbers(self):
        result = parse("tss BETWEEN 50 AND 100")
        assert isinstance(result.conditions, Between)
        assert result.conditions.field == "tss"
        assert result.conditions.low == NumberValue(value=50.0, unit=None)
        assert result.conditions.high == NumberValue(value=100.0, unit=None)

    def test_between_dates(self):
        result = parse("date BETWEEN 2026-01-01 AND 2026-06-30")
        assert isinstance(result.conditions, Between)
        assert isinstance(result.conditions.low, DateValue)
        assert isinstance(result.conditions.high, DateValue)

    def test_between_with_units(self):
        result = parse("distance BETWEEN 50km AND 100km")
        assert isinstance(result.conditions, Between)
        assert result.conditions.low == NumberValue(value=50.0, unit="km")
        assert result.conditions.high == NumberValue(value=100.0, unit="km")


class TestInOperator:
    """Test IN and NOT IN expressions."""

    def test_in_strings(self):
        result = parse('source IN ("xert", "garmin")')
        assert isinstance(result.conditions, InList)
        assert result.conditions.field == "source"
        assert result.conditions.negated is False
        assert len(result.conditions.values) == 2
        assert result.conditions.values[0] == StringValue(value="xert")

    def test_not_in(self):
        result = parse('source NOT IN ("upload")')
        assert isinstance(result.conditions, InList)
        assert result.conditions.negated is True

    def test_in_numbers(self):
        result = parse("tss IN (100, 150, 200)")
        assert isinstance(result.conditions, InList)
        assert len(result.conditions.values) == 3


class TestNullChecks:
    """Test IS NULL and IS NOT NULL."""

    def test_is_null(self):
        result = parse("power IS NULL")
        assert isinstance(result.conditions, NullCheck)
        assert result.conditions.field == "power"
        assert result.conditions.is_null is True

    def test_is_not_null(self):
        result = parse("power IS NOT NULL")
        assert isinstance(result.conditions, NullCheck)
        assert result.conditions.is_null is False


class TestTextMatching:
    """Test text matching operators."""

    def test_contains(self):
        result = parse('title CONTAINS "recovery"')
        assert isinstance(result.conditions, TextMatch)
        assert result.conditions.field == "title"
        assert result.conditions.op == "CONTAINS"
        assert result.conditions.value == "recovery"

    def test_starts_with(self):
        result = parse('title STARTS WITH "Morning"')
        assert isinstance(result.conditions, TextMatch)
        assert result.conditions.op == "STARTS_WITH"

    def test_ends_with(self):
        result = parse('title ENDS WITH "Ride"')
        assert isinstance(result.conditions, TextMatch)
        assert result.conditions.op == "ENDS_WITH"


class TestSelectClause:
    """Test SELECT projections."""

    def test_select_all(self):
        result = parse("SELECT * WHERE tss > 100")
        assert result.projection.kind == "all"

    def test_select_view_summary(self):
        result = parse("SELECT summary WHERE tss > 100")
        assert result.projection.kind == "view"
        assert result.projection.view == "summary"

    def test_select_view_power(self):
        result = parse("SELECT power WHERE tss > 100")
        assert result.projection.view == "power"

    def test_select_view_hr(self):
        result = parse("SELECT hr WHERE tss > 100")
        assert result.projection.view == "hr"

    def test_select_view_full(self):
        result = parse("SELECT full WHERE tss > 100")
        assert result.projection.view == "full"

    def test_select_fields(self):
        result = parse("SELECT tss, distance, elevation WHERE tss > 100")
        assert result.projection.kind == "fields"
        assert result.projection.fields == ["tss", "distance", "elevation"]


class TestOrderByClause:
    """Test ORDER BY clause."""

    def test_order_by_desc(self):
        result = parse("tss > 100 ORDER BY elevation DESC")
        assert result.order_by is not None
        assert len(result.order_by) == 1
        assert result.order_by[0] == OrderItem(field="elevation", direction="DESC")

    def test_order_by_asc(self):
        result = parse("tss > 100 ORDER BY date ASC")
        assert result.order_by[0].direction == "ASC"

    def test_order_by_default_desc(self):
        result = parse("tss > 100 ORDER BY elevation")
        assert result.order_by[0].direction == "DESC"

    def test_order_by_multiple(self):
        result = parse("tss > 100 ORDER BY date DESC, tss DESC")
        assert len(result.order_by) == 2
        assert result.order_by[0].field == "date"
        assert result.order_by[1].field == "tss"

    def test_order_by_only(self):
        result = parse("ORDER BY elevation DESC")
        assert result.conditions is None
        assert result.order_by is not None


class TestLimitClause:
    """Test LIMIT clause."""

    def test_limit(self):
        result = parse("tss > 100 LIMIT 10")
        assert result.limit == 10

    def test_limit_with_order(self):
        result = parse("tss > 100 ORDER BY elevation DESC LIMIT 10")
        assert result.limit == 10
        assert result.order_by is not None

    def test_limit_only(self):
        result = parse("LIMIT 20")
        assert result.limit == 20
        assert result.conditions is None


class TestAggregations:
    """Test aggregation queries."""

    def test_count_star(self):
        result = parse("COUNT(*)")
        assert result.type == "aggregate"
        assert result.projection.kind == "aggregates"
        assert len(result.projection.aggregates) == 1
        assert result.projection.aggregates[0] == AggExpr(func="COUNT", field=None)

    def test_avg(self):
        result = parse("AVG(tss)")
        assert result.projection.aggregates[0] == AggExpr(func="AVG", field="tss")

    def test_sum(self):
        result = parse("SUM(distance)")
        assert result.projection.aggregates[0] == AggExpr(func="SUM", field="distance")

    def test_min(self):
        result = parse("MIN(duration)")
        assert result.projection.aggregates[0] == AggExpr(func="MIN", field="duration")

    def test_max(self):
        result = parse("MAX(elevation)")
        assert result.projection.aggregates[0] == AggExpr(func="MAX", field="elevation")

    def test_multiple_aggregates(self):
        result = parse("COUNT(*), AVG(tss), SUM(distance)")
        assert len(result.projection.aggregates) == 3

    def test_aggregate_with_where(self):
        result = parse("AVG(tss) WHERE date >= START_OF_YEAR")
        assert result.type == "aggregate"
        assert result.conditions is not None

    def test_case_insensitive(self):
        result = parse("count(*)")
        assert result.projection.aggregates[0].func == "COUNT"


class TestGroupByClause:
    """Test GROUP BY clause."""

    def test_group_by_month(self):
        result = parse("COUNT(*) GROUP BY month")
        assert result.group_by is not None
        assert len(result.group_by) == 1
        assert result.group_by[0] == GroupKey(kind="time_bucket", value="month")

    def test_group_by_week(self):
        result = parse("AVG(tss) GROUP BY week")
        assert result.group_by[0].value == "week"

    def test_group_by_day(self):
        result = parse("SUM(distance) GROUP BY day")
        assert result.group_by[0].value == "day"

    def test_group_by_year(self):
        result = parse("COUNT(*) GROUP BY year")
        assert result.group_by[0].value == "year"

    def test_group_by_field(self):
        result = parse("COUNT(*) GROUP BY source")
        assert result.group_by[0] == GroupKey(kind="field", value="source")

    def test_group_by_multiple(self):
        result = parse("COUNT(*) GROUP BY month, source")
        assert len(result.group_by) == 2


class TestAllActivitiesQuery:
    """Test the * query for all activities."""

    def test_star_only(self):
        result = parse("*")
        assert result.type == "list"
        assert result.projection.kind == "all"
        assert result.conditions is None


class TestComplexQueries:
    """Test complex real-world queries."""

    def test_full_list_query(self):
        result = parse(
            'SELECT summary WHERE tss > 100 AND source IN ("xert", "garmin") '
            "ORDER BY date DESC LIMIT 20"
        )
        assert result.type == "list"
        assert result.projection.view == "summary"
        assert isinstance(result.conditions, BinaryOp)
        assert result.order_by is not None
        assert result.limit == 20

    def test_complex_conditions(self):
        result = parse(
            "(tss > 100 OR breakthrough = true) AND date >= START_OF_YEAR"
        )
        assert isinstance(result.conditions, BinaryOp)
        assert result.conditions.op == "AND"

    def test_aggregation_with_filter_and_group(self):
        result = parse(
            "COUNT(*), AVG(tss), SUM(distance) WHERE date >= START_OF_YEAR GROUP BY month"
        )
        assert result.type == "aggregate"
        assert len(result.projection.aggregates) == 3
        assert result.conditions is not None
        assert result.group_by is not None


class TestParseErrors:
    """Test error handling."""

    def test_empty_query(self):
        with pytest.raises(ParseError) as exc:
            parse("")
        assert "Empty query" in exc.value.message

    def test_whitespace_only(self):
        with pytest.raises(ParseError) as exc:
            parse("   ")
        assert "Empty query" in exc.value.message

    def test_unexpected_token(self):
        with pytest.raises(ParseError) as exc:
            parse("tss > AND distance")
        assert exc.value.column > 0

    def test_incomplete_expression(self):
        with pytest.raises(ParseError):
            parse("tss >")

    def test_invalid_operator(self):
        with pytest.raises(ParseError):
            parse("tss <> 100")  # <> not supported

    def test_unclosed_parenthesis(self):
        with pytest.raises(ParseError):
            parse("(tss > 100 AND distance > 50km")

    def test_error_has_line_column(self):
        with pytest.raises(ParseError) as exc:
            parse("tss > 100 AND AND distance > 50")
        assert exc.value.line >= 1
        assert exc.value.column >= 1

    def test_error_context(self):
        with pytest.raises(ParseError) as exc:
            parse("tss > 100 AND AND distance > 50")
        context = exc.value.get_context("tss > 100 AND AND distance > 50")
        assert "^" in context


class TestCaseSensitivity:
    """Test case sensitivity rules."""

    def test_keywords_case_insensitive(self):
        result = parse("SELECT summary where TSS > 100 order BY date DESC")
        assert result.projection is not None
        assert result.conditions is not None
        assert result.order_by is not None

    def test_field_names_preserved(self):
        result = parse("TSS > 100")
        assert result.conditions.field == "TSS"  # Original case preserved

    def test_aggregation_func_case_insensitive(self):
        result = parse("avg(tss)")
        assert result.projection.aggregates[0].func == "AVG"
