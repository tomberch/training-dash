"""AST node definitions for the query DSL."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# === Top Level ===


@dataclass
class Query:
    """Root AST node representing a complete query."""

    type: Literal["list", "aggregate"]
    projection: "Projection | None"
    conditions: "Expr | None"
    group_by: list["GroupKey"] | None
    order_by: list["OrderItem"] | None
    limit: int | None


# === Projection ===


@dataclass
class Projection:
    """What fields to return in the result."""

    kind: Literal["all", "view", "fields", "aggregates"]
    view: str | None = None  # "summary", "power", "hr", "full"
    fields: list[str] | None = None
    aggregates: list["AggExpr"] | None = None


@dataclass
class AggExpr:
    """An aggregation expression like COUNT(*) or AVG(tss)."""

    func: Literal["COUNT", "SUM", "AVG", "MIN", "MAX"]
    field: str | None  # None for COUNT(*)


@dataclass
class GroupKey:
    """A GROUP BY key - either a time bucket or a field."""

    kind: Literal["time_bucket", "field"]
    value: str  # "month", "week", etc. or field name


@dataclass
class OrderItem:
    """An ORDER BY item with field and direction."""

    field: str
    direction: Literal["ASC", "DESC"]


# === Expressions ===


@dataclass
class BinaryOp:
    """Binary logical operation (AND/OR)."""

    op: Literal["AND", "OR"]
    left: "Expr"
    right: "Expr"


@dataclass
class NotOp:
    """Logical NOT operation."""

    expr: "Expr"


@dataclass
class Comparison:
    """Field comparison with an operator and value."""

    field: str
    op: Literal["=", "!=", ">", ">=", "<", "<="]
    value: "Value"


@dataclass
class Between:
    """BETWEEN expression for range checks."""

    field: str
    low: "Value"
    high: "Value"


@dataclass
class InList:
    """IN or NOT IN expression for set membership."""

    field: str
    values: list["Value"]
    negated: bool


@dataclass
class NullCheck:
    """IS NULL or IS NOT NULL check."""

    field: str
    is_null: bool  # True for IS NULL, False for IS NOT NULL


@dataclass
class TextMatch:
    """Text matching operations (CONTAINS, STARTS WITH, ENDS WITH)."""

    field: str
    op: Literal["CONTAINS", "STARTS_WITH", "ENDS_WITH"]
    value: str


@dataclass
class BooleanField:
    """Standalone boolean field (treated as field = true)."""

    field: str


# Expression union type
Expr = BinaryOp | NotOp | Comparison | Between | InList | NullCheck | TextMatch | BooleanField


# === Values ===


@dataclass
class NumberValue:
    """A numeric value with optional unit."""

    value: float
    unit: str | None = None  # "km", "mi", "h", etc.


@dataclass
class StringValue:
    """A string literal value."""

    value: str


@dataclass
class DateValue:
    """An absolute date/datetime value."""

    value: datetime


@dataclass
class RelativeDate:
    """A relative date expression like NOW - 30d."""

    base: Literal["NOW", "TODAY", "START_OF_DAY", "START_OF_WEEK", "START_OF_MONTH", "START_OF_YEAR"]
    offset_days: int | None = None  # Positive or negative offset in days


@dataclass
class BoolValue:
    """A boolean literal value."""

    value: bool


@dataclass
class DurationValue:
    """A duration value in seconds (from colon format like 1:30:00)."""

    seconds: int


# Value union type
Value = NumberValue | StringValue | DateValue | RelativeDate | BoolValue | DurationValue
