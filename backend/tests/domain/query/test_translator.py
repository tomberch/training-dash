"""Tests for the query translator."""

from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from trainingdash.domain.query import (
    GroupedAggResult,
    ListQueryResult,
    ScalarAggResult,
    parse,
    translate,
    validate,
)


def _compile_sql(query) -> str:
    """Compile a SQLAlchemy query to a string for testing."""
    compiled = query.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled)


def _normalize_sql(sql: str) -> str:
    """Normalize SQL for comparison (remove extra whitespace)."""
    return " ".join(sql.split())


class TestSimpleComparisons:
    """Test translation of simple comparison expressions."""

    def test_greater_than(self):
        query = parse("tss > 100")
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert isinstance(result, ListQueryResult)
        sql = _compile_sql(result.query)
        assert "activities.tss > 100" in sql
        assert "activities.user_id = 1" in sql

    def test_equals(self):
        query = parse('source = "xert"')
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.source = 'xert'" in sql

    def test_not_equals(self):
        query = parse('source != "upload"')
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.source != 'upload'" in sql

    def test_less_than_equal(self):
        query = parse("intensity_factor <= 0.9")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.intensity_factor <= 0.9" in sql


class TestUnitConversion:
    """Test that units are properly converted before translation."""

    def test_distance_km(self):
        query = parse("distance > 50km")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        # 50km should be converted to 50000m
        assert "activities.total_distance_m > 50000" in sql

    def test_speed_kph(self):
        query = parse("speed > 30kph")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        # 30 kph should be converted to ~8.33 mps
        assert "activities.avg_speed_mps > 8.33" in sql


class TestLogicalOperators:
    """Test AND, OR, NOT translation."""

    def test_and(self):
        query = parse("tss > 100 AND distance > 50km")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.tss > 100" in sql
        assert "activities.total_distance_m > 50000" in sql
        assert "AND" in sql

    def test_or(self):
        query = parse("tss > 200 OR breakthrough = true")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.tss > 200" in sql
        assert "activities.is_breakthrough" in sql
        assert "OR" in sql

    def test_not(self):
        query = parse("NOT breakthrough = true")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        # NOT may be expressed as != true or explicit NOT
        assert ("NOT" in sql) or ("!= true" in sql)

    def test_complex_precedence(self):
        query = parse("(tss > 100 OR breakthrough = true) AND distance > 50km")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        # Should have proper grouping
        assert "AND" in sql
        assert "OR" in sql


class TestBetweenOperator:
    """Test BETWEEN translation."""

    def test_between_numbers(self):
        query = parse("tss BETWEEN 50 AND 150")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.tss BETWEEN 50" in sql
        assert "AND 150" in sql

    def test_between_dates(self):
        query = parse("date BETWEEN 2026-01-01 AND 2026-06-30")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.started_at BETWEEN" in sql
        assert "2026-01-01" in sql
        assert "2026-06-30" in sql


class TestInOperator:
    """Test IN and NOT IN translation."""

    def test_in_strings(self):
        query = parse('source IN ("xert", "garmin")')
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.source IN" in sql
        assert "'xert'" in sql
        assert "'garmin'" in sql

    def test_not_in(self):
        query = parse('source NOT IN ("upload")')
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.source NOT IN" in sql


class TestNullChecks:
    """Test IS NULL / IS NOT NULL translation."""

    def test_is_null(self):
        query = parse("power IS NULL")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.avg_power_w IS NULL" in sql

    def test_is_not_null(self):
        query = parse("power IS NOT NULL")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.avg_power_w IS NOT NULL" in sql


class TestTextMatching:
    """Test text matching translation."""

    def test_contains(self):
        query = parse('title CONTAINS "recovery"')
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        # Should use ILIKE for case-insensitive
        assert "ILIKE" in sql.upper()
        assert "%recovery%" in sql

    def test_starts_with(self):
        query = parse('title STARTS WITH "Morning"')
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "ILIKE" in sql.upper()
        # SQLAlchemy doubles % for literal binding
        assert "Morning%" in sql or "Morning%%" in sql

    def test_ends_with(self):
        query = parse('title ENDS WITH "Ride"')
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "ILIKE" in sql.upper()
        # SQLAlchemy doubles % for literal binding
        assert "%Ride" in sql or "%%Ride" in sql


class TestBooleanFields:
    """Test boolean field translation."""

    def test_boolean_comparison(self):
        query = parse("breakthrough = true")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.is_breakthrough = true" in sql

    def test_standalone_boolean(self):
        query = parse("breakthrough")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.is_breakthrough = true" in sql


class TestOrderBy:
    """Test ORDER BY translation."""

    def test_order_by_desc(self):
        query = parse("tss > 100 ORDER BY elevation DESC")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "ORDER BY activities.elevation_gain_m DESC" in sql

    def test_order_by_asc(self):
        query = parse("tss > 100 ORDER BY date ASC")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "ORDER BY activities.started_at ASC" in sql

    def test_order_by_multiple(self):
        query = parse("tss > 100 ORDER BY date DESC, tss DESC")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "activities.started_at DESC" in sql
        assert "activities.tss DESC" in sql

    def test_default_order(self):
        query = parse("tss > 100")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        # Default should be date DESC
        assert "ORDER BY activities.started_at DESC" in sql


class TestLimit:
    """Test LIMIT translation."""

    def test_limit(self):
        query = parse("tss > 100 LIMIT 10")
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert result.has_explicit_limit is True
        sql = _compile_sql(result.query)
        assert "LIMIT 10" in sql

    def test_no_limit(self):
        query = parse("tss > 100")
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert result.has_explicit_limit is False
        sql = _compile_sql(result.query)
        assert "LIMIT" not in sql


class TestUserScoping:
    """Test that queries are always scoped to the user."""

    def test_user_scoping(self):
        query = parse("tss > 100")
        validated = validate(query)
        result = translate(validated, user_id=42)

        sql = _compile_sql(result.query)
        assert "activities.user_id = 42" in sql

    def test_user_scoping_complex_query(self):
        query = parse("(tss > 100 OR breakthrough = true) AND distance > 50km")
        validated = validate(query)
        result = translate(validated, user_id=7)

        sql = _compile_sql(result.query)
        assert "activities.user_id = 7" in sql


class TestAggregations:
    """Test aggregation query translation."""

    def test_count_star(self):
        query = parse("COUNT(*)")
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert isinstance(result, ScalarAggResult)
        sql = _compile_sql(result.query)
        assert "count(" in sql.lower()

    def test_sum(self):
        query = parse("SUM(distance)")
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert isinstance(result, ScalarAggResult)
        sql = _compile_sql(result.query)
        assert "sum(activities.total_distance_m)" in sql.lower()

    def test_avg(self):
        query = parse("AVG(tss)")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "avg(activities.tss)" in sql.lower()

    def test_min_max(self):
        query = parse("MIN(tss), MAX(tss)")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "min(activities.tss)" in sql.lower()
        assert "max(activities.tss)" in sql.lower()

    def test_aggregate_with_filter(self):
        query = parse("AVG(tss) WHERE date >= START_OF_YEAR")
        now = datetime(2026, 8, 14)
        validated = validate(query, now=now)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "avg(activities.tss)" in sql.lower()
        assert "activities.started_at >=" in sql
        assert "2026-01-01" in sql

    def test_multiple_aggregates(self):
        query = parse("COUNT(*), AVG(tss), SUM(distance)")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "count(" in sql.lower()
        assert "avg(" in sql.lower()
        assert "sum(" in sql.lower()


class TestGroupBy:
    """Test GROUP BY translation."""

    def test_group_by_month(self):
        query = parse("COUNT(*) GROUP BY month")
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert isinstance(result, GroupedAggResult)
        assert "bucket_month" in result.group_columns
        sql = _compile_sql(result.query)
        assert "date_trunc('month'" in sql.lower()
        assert "GROUP BY" in sql

    def test_group_by_week(self):
        query = parse("SUM(distance) GROUP BY week")
        validated = validate(query)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "date_trunc('week'" in sql.lower()

    def test_group_by_field(self):
        query = parse("COUNT(*) GROUP BY source")
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert "source" in result.group_columns
        sql = _compile_sql(result.query)
        assert "activities.source" in sql
        assert "GROUP BY" in sql

    def test_group_by_multiple(self):
        query = parse("COUNT(*) GROUP BY month, source")
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert len(result.group_columns) == 2
        sql = _compile_sql(result.query)
        assert "date_trunc('month'" in sql.lower()
        assert "activities.source" in sql


class TestRelativeDates:
    """Test relative date resolution in translation."""

    def test_now(self):
        query = parse("date >= NOW")
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "2026-08-14 12:00:00" in sql

    def test_start_of_month(self):
        query = parse("date >= START_OF_MONTH")
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "2026-08-01 00:00:00" in sql

    def test_now_minus_days(self):
        query = parse("date >= NOW - 30d")
        now = datetime(2026, 8, 14, 12, 0, 0)
        validated = validate(query, now=now)
        result = translate(validated, user_id=1)

        sql = _compile_sql(result.query)
        assert "2026-07-15" in sql


class TestComplexQueries:
    """Test complex real-world queries."""

    def test_full_list_query(self):
        query = parse(
            'SELECT summary WHERE tss > 100 AND source IN ("xert", "garmin") '
            "ORDER BY date DESC LIMIT 20"
        )
        validated = validate(query)
        result = translate(validated, user_id=1)

        assert isinstance(result, ListQueryResult)
        assert result.has_explicit_limit is True
        sql = _compile_sql(result.query)
        assert "activities.tss > 100" in sql
        assert "activities.source IN" in sql
        assert "ORDER BY activities.started_at DESC" in sql
        assert "LIMIT 20" in sql
        assert "activities.user_id = 1" in sql

    def test_aggregation_with_group_and_filter(self):
        query = parse(
            "COUNT(*), AVG(tss), SUM(distance) WHERE date >= START_OF_YEAR GROUP BY month"
        )
        now = datetime(2026, 8, 14)
        validated = validate(query, now=now)
        result = translate(validated, user_id=1)

        assert isinstance(result, GroupedAggResult)
        sql = _compile_sql(result.query)
        assert "count(" in sql.lower()
        assert "avg(" in sql.lower()
        assert "sum(" in sql.lower()
        assert "activities.started_at >= '2026-01-01" in sql
        assert "GROUP BY" in sql


class TestResultTypes:
    """Test that correct result types are returned."""

    def test_list_query_returns_list_result(self):
        query = parse("tss > 100")
        validated = validate(query)
        result = translate(validated, user_id=1)
        assert isinstance(result, ListQueryResult)

    def test_scalar_agg_returns_scalar_result(self):
        query = parse("COUNT(*)")
        validated = validate(query)
        result = translate(validated, user_id=1)
        assert isinstance(result, ScalarAggResult)

    def test_grouped_agg_returns_grouped_result(self):
        query = parse("COUNT(*) GROUP BY month")
        validated = validate(query)
        result = translate(validated, user_id=1)
        assert isinstance(result, GroupedAggResult)
