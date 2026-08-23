"""Translator that converts validated AST to SQLAlchemy query expressions.

The translator produces SQLAlchemy expressions that can be executed against
the Activity table. It handles:
- WHERE clause conditions
- ORDER BY clauses
- LIMIT/pagination
- Aggregations (COUNT, SUM, AVG, MIN, MAX)
- GROUP BY (fields and time buckets)
- User scoping (always injected)
- Zone time fields (computed from JSON columns)
"""

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, and_, cast, func, not_, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.types import Integer

from trainingdash.repositories.postgres.models import Activity

from .ast import (
    Between,
    BinaryOp,
    BooleanField,
    BoolValue,
    Comparison,
    DateValue,
    InList,
    NotOp,
    NullCheck,
    NumberValue,
    StringValue,
    TextMatch,
)
from .fields import FIELD_DEFINITIONS
from .validator import ValidatedQuery


# Zone field patterns for extracting zone number from field name
POWER_ZONE_PATTERN = re.compile(r"^power_zone_(\d+)_s$")
HR_ZONE_PATTERN = re.compile(r"^hr_zone_(\d+)_s$")


@dataclass
class ListQueryResult:
    """Result of translating a list query."""

    query: Select[tuple[Activity]]
    has_explicit_limit: bool


@dataclass
class ScalarAggResult:
    """Result of a scalar aggregation (no GROUP BY)."""

    query: Select[tuple[Any, ...]]


@dataclass
class GroupedAggResult:
    """Result of a grouped aggregation."""

    query: Select[tuple[Any, ...]]
    group_columns: list[str]


TranslatedQuery = ListQueryResult | ScalarAggResult | GroupedAggResult


def _get_column(field_name: str) -> ColumnElement:
    """Get the SQLAlchemy column for a field name.

    Handles both regular columns and computed zone time fields.
    Zone time fields (e.g., power_zone_3_s) are extracted from JSON columns.
    """
    # Check if it's a power zone field
    power_match = POWER_ZONE_PATTERN.match(field_name)
    if power_match:
        zone_num = power_match.group(1)
        # Extract from power_zone_times JSON: {"1": 100, "2": 200, ...}
        # Cast the text column to JSONB, then extract the zone value as integer
        return cast(
            cast(Activity.power_zone_times, JSONB)[zone_num].astext,
            Integer,
        )

    # Check if it's an HR zone field
    hr_match = HR_ZONE_PATTERN.match(field_name)
    if hr_match:
        zone_num = hr_match.group(1)
        # Extract from hr_zone_times JSON
        return cast(
            cast(Activity.hr_zone_times, JSONB)[zone_num].astext,
            Integer,
        )

    # Regular column
    return getattr(Activity, field_name)


def _is_computed_field(field_name: str) -> bool:
    """Check if a field is computed (not a direct database column)."""
    field_def = FIELD_DEFINITIONS.get(field_name)
    return field_def is not None and field_def.computed


def _translate_value(value: Any) -> Any:
    """Convert an AST value to a Python value for SQLAlchemy."""
    if isinstance(value, NumberValue):
        return value.value
    if isinstance(value, StringValue):
        return value.value
    if isinstance(value, DateValue):
        return value.value
    if isinstance(value, BoolValue):
        return value.value
    return value


def translate_expr(expr: Any) -> ColumnElement:
    """Translate an expression AST node to a SQLAlchemy expression.

    Args:
        expr: A validated expression node (Comparison, BinaryOp, etc.)

    Returns:
        A SQLAlchemy column expression
    """
    if isinstance(expr, BinaryOp):
        left = translate_expr(expr.left)
        right = translate_expr(expr.right)
        if expr.op == "AND":
            return and_(left, right)
        return or_(left, right)

    if isinstance(expr, NotOp):
        inner = translate_expr(expr.expr)
        return not_(inner)

    if isinstance(expr, Comparison):
        return _translate_comparison(expr)

    if isinstance(expr, Between):
        return _translate_between(expr)

    if isinstance(expr, InList):
        return _translate_in_list(expr)

    if isinstance(expr, NullCheck):
        return _translate_null_check(expr)

    if isinstance(expr, TextMatch):
        return _translate_text_match(expr)

    if isinstance(expr, BooleanField):
        # Standalone boolean field is treated as field = True
        col = _get_column(expr.field)
        return col == True

    raise ValueError(f"Unknown expression type: {type(expr)}")


def _translate_comparison(comp: Comparison) -> ColumnElement:
    """Translate a comparison expression."""
    col = _get_column(comp.field)
    value = _translate_value(comp.value)

    if comp.op == "=":
        return col == value
    if comp.op == "!=":
        return col != value
    if comp.op == ">":
        return col > value
    if comp.op == ">=":
        return col >= value
    if comp.op == "<":
        return col < value
    if comp.op == "<=":
        return col <= value

    raise ValueError(f"Unknown comparison operator: {comp.op}")


def _translate_between(between: Between) -> ColumnElement:
    """Translate a BETWEEN expression."""
    col = _get_column(between.field)
    low = _translate_value(between.low)
    high = _translate_value(between.high)
    return col.between(low, high)


def _translate_in_list(in_list: InList) -> ColumnElement:
    """Translate an IN or NOT IN expression."""
    col = _get_column(in_list.field)
    values = [_translate_value(v) for v in in_list.values]

    if in_list.negated:
        return col.notin_(values)
    return col.in_(values)


def _translate_null_check(null_check: NullCheck) -> ColumnElement:
    """Translate IS NULL or IS NOT NULL."""
    col = _get_column(null_check.field)
    if null_check.is_null:
        return col.is_(None)
    return col.isnot(None)


def _translate_text_match(text_match: TextMatch) -> ColumnElement:
    """Translate text matching (CONTAINS, STARTS WITH, ENDS WITH)."""
    col = _get_column(text_match.field)
    value = text_match.value

    # Use ilike for case-insensitive matching
    if text_match.op == "CONTAINS":
        return col.ilike(f"%{value}%")
    if text_match.op == "STARTS_WITH":
        return col.ilike(f"{value}%")
    if text_match.op == "ENDS_WITH":
        return col.ilike(f"%{value}")

    raise ValueError(f"Unknown text match operator: {text_match.op}")


def _translate_aggregation(func_name: str, field: str | None) -> ColumnElement:
    """Translate an aggregation function."""
    if func_name == "COUNT":
        if field is None:
            return func.count()
        return func.count(_get_column(field))

    if field is None:
        raise ValueError(f"{func_name}(*) is not valid")

    col = _get_column(field)

    if func_name == "SUM":
        return func.sum(col)
    if func_name == "AVG":
        return func.avg(col)
    if func_name == "MIN":
        return func.min(col)
    if func_name == "MAX":
        return func.max(col)

    raise ValueError(f"Unknown aggregation function: {func_name}")


def _translate_time_bucket(bucket: str, base_col: ColumnElement = None) -> ColumnElement:
    """Translate a time bucket to a GROUP BY expression.

    Uses started_at as the base column for time bucketing.
    """
    col = base_col or Activity.started_at

    if bucket == "day":
        return func.date_trunc("day", col)
    if bucket == "week":
        return func.date_trunc("week", col)
    if bucket == "month":
        return func.date_trunc("month", col)
    if bucket == "year":
        return func.date_trunc("year", col)

    raise ValueError(f"Unknown time bucket: {bucket}")


class QueryTranslator:
    """Translates validated queries to SQLAlchemy expressions."""

    def __init__(self, user_id: int):
        """Initialize the translator.

        Args:
            user_id: The user ID to scope all queries to.
        """
        self._user_id = user_id

    def translate(self, validated: ValidatedQuery) -> TranslatedQuery:
        """Translate a validated query to SQLAlchemy.

        Args:
            validated: A validated query from the validator

        Returns:
            A TranslatedQuery (ListQueryResult, ScalarAggResult, or GroupedAggResult)
        """
        if validated.type == "list":
            return self._translate_list_query(validated)
        return self._translate_agg_query(validated)

    def _translate_list_query(self, validated: ValidatedQuery) -> ListQueryResult:
        """Translate a list query (returns activities)."""
        # Start with base query
        query = select(Activity)

        # Always scope to user
        query = query.where(Activity.user_id == self._user_id)

        # Apply WHERE conditions
        if validated.conditions:
            query = query.where(translate_expr(validated.conditions))

        # Apply ORDER BY
        if validated.order_by:
            for item in validated.order_by:
                col = _get_column(item.field)
                if item.direction == "DESC":
                    col = col.desc()
                else:
                    col = col.asc()
                query = query.order_by(col)
        else:
            # Default: order by date descending
            query = query.order_by(Activity.started_at.desc())

        # Apply LIMIT
        has_explicit_limit = validated.limit is not None
        if has_explicit_limit:
            query = query.limit(validated.limit)

        return ListQueryResult(query=query, has_explicit_limit=has_explicit_limit)

    def _translate_agg_query(self, validated: ValidatedQuery) -> ScalarAggResult | GroupedAggResult:
        """Translate an aggregation query."""
        # Build aggregation columns
        agg_columns = []
        if validated.projection and validated.projection.aggregates:
            for agg in validated.projection.aggregates:
                agg_col = _translate_aggregation(agg.func, agg.field)
                # Label with function and field name
                label = f"{agg.func.lower()}_{agg.field or 'all'}"
                agg_columns.append(agg_col.label(label))

        # Build GROUP BY columns
        group_columns = []
        group_labels = []
        if validated.group_by:
            for key in validated.group_by:
                if key.kind == "time_bucket":
                    col = _translate_time_bucket(key.value)
                    label = f"bucket_{key.value}"
                else:
                    col = _get_column(key.value)
                    label = key.value
                group_columns.append(col.label(label))
                group_labels.append(label)

        # Build the SELECT
        select_cols = group_columns + agg_columns
        query = select(*select_cols)

        # Always scope to user (select_from Activity)
        query = query.select_from(Activity).where(Activity.user_id == self._user_id)

        # Apply WHERE conditions
        if validated.conditions:
            query = query.where(translate_expr(validated.conditions))

        # Apply GROUP BY
        if group_columns:
            # Group by the labeled columns
            query = query.group_by(*list(group_columns))

            # Order by the first group column
            first_group = group_columns[0]
            query = query.order_by(first_group)

            return GroupedAggResult(query=query, group_columns=group_labels)

        return ScalarAggResult(query=query)


def translate(
    validated: ValidatedQuery,
    user_id: int,
) -> TranslatedQuery:
    """Translate a validated query to SQLAlchemy.

    Convenience function that creates a QueryTranslator and translates.

    Args:
        validated: A validated query from the validator
        user_id: The user ID to scope all queries to

    Returns:
        A TranslatedQuery ready for execution
    """
    translator = QueryTranslator(user_id=user_id)
    return translator.translate(validated)
