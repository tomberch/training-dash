"""Lark transformer that converts parse tree to typed AST."""

from datetime import datetime
from typing import Any

from lark import Token, Transformer, v_args

from .ast import (
    AggExpr,
    Between,
    BinaryOp,
    BooleanField,
    BoolValue,
    Comparison,
    DateValue,
    DurationValue,
    Expr,
    GroupKey,
    InList,
    NotOp,
    NullCheck,
    NumberValue,
    OrderItem,
    Projection,
    Query,
    RelativeDate,
    StringValue,
    TextMatch,
    Value,
)


def _filter_tokens(items: list) -> list:
    """Filter out Token instances from a list of items."""
    return [item for item in items if not isinstance(item, Token)]


def _first_of_type(items: list, *types) -> Any | None:
    """Return the first item matching one of the given types, or None."""
    for item in items:
        if isinstance(item, types):
            return item
    return None


class QueryTransformer(Transformer):
    """Transform Lark parse tree into typed AST nodes."""

    # === Top Level ===

    def _build_list_query(
        self,
        items: list,
        *,
        include_projection: bool = False,
        include_conditions: bool = False,
    ) -> Query:
        """Helper to build a list query from items, extracting order_by and limit."""
        projection = None
        conditions = None
        order_by = None
        limit = None

        for item in items:
            if isinstance(item, Token):
                continue
            if include_projection and isinstance(item, Projection):
                projection = item
            elif isinstance(item, list) and item and isinstance(item[0], OrderItem):
                order_by = item
            elif isinstance(item, int):
                limit = item
            elif include_conditions and item is not None:
                conditions = item

        return Query(
            type="list",
            projection=projection,
            conditions=conditions,
            group_by=None,
            order_by=order_by,
            limit=limit,
        )

    def list_query(self, items: list) -> Query:
        """SELECT ... WHERE ... ORDER BY ... LIMIT ..."""
        return self._build_list_query(items, include_projection=True, include_conditions=True)

    def list_query_no_select(self, items: list) -> Query:
        """WHERE ... ORDER BY ... LIMIT ..."""
        return self._build_list_query(items, include_conditions=True)

    def list_query_order_only(self, items: list) -> Query:
        """ORDER BY ... LIMIT ..."""
        return self._build_list_query(items)

    def list_query_limit_only(self, items: list) -> Query:
        """LIMIT ..."""
        limit = _first_of_type(items, int)
        return Query(
            type="list",
            projection=None,
            conditions=None,
            group_by=None,
            order_by=None,
            limit=limit,
        )

    def list_query_expr(self, items: list) -> Query:
        """expr ORDER BY ... LIMIT ... (condition without WHERE)."""
        return self._build_list_query(items, include_conditions=True)

    def list_query_all(self, items: list) -> Query:
        """* (all activities)."""
        return Query(
            type="list",
            projection=Projection(kind="all"),
            conditions=None,
            group_by=None,
            order_by=None,
            limit=None,
        )

    def agg_query(self, items: list) -> Query:
        """Aggregation query with optional WHERE and GROUP BY."""
        aggregates = []
        conditions = None
        group_by = None

        for item in items:
            if isinstance(item, list):
                if item and isinstance(item[0], AggExpr):
                    aggregates = item
                elif item and isinstance(item[0], GroupKey):
                    group_by = item
            elif isinstance(item, (Comparison, BinaryOp, NotOp, Between, InList, NullCheck, TextMatch, BooleanField)):
                conditions = item

        return Query(
            type="aggregate",
            projection=Projection(kind="aggregates", aggregates=aggregates),
            conditions=conditions,
            group_by=group_by,
            order_by=None,
            limit=None,
        )

    # === Clauses ===

    def select_clause(self, items: list) -> Projection:
        """Extract projection from SELECT clause."""
        return _first_of_type(items, Projection) or items[-1]

    def proj_all(self, items: list) -> Projection:
        """SELECT *."""
        return Projection(kind="all")

    def proj_view(self, items: list) -> Projection:
        """SELECT <view_name>."""
        view_name = str(items[0]).lower()
        return Projection(kind="view", view=view_name)

    def proj_fields(self, items: list) -> Projection:
        """SELECT field1, field2, ..."""
        fields = [str(f) for f in items[0]]
        return Projection(kind="fields", fields=fields)

    def view_name(self, items: list) -> str:
        """View name token."""
        return str(items[0]).lower()

    def field_list(self, items: list) -> list[str]:
        """Comma-separated field names."""
        return [str(f) for f in items]

    def where_clause(self, items: list) -> Expr:
        """Extract expression from WHERE clause."""
        non_tokens = _filter_tokens(items)
        return non_tokens[0] if non_tokens else items[-1]

    def order_clause(self, items: list) -> list[OrderItem]:
        """Extract OrderItems from ORDER BY clause."""
        return [item for item in items if isinstance(item, OrderItem)]

    def order_item(self, items: list) -> OrderItem:
        """Single ORDER BY item with optional direction."""
        field = str(items[0])
        direction = items[1] if len(items) > 1 else "DESC"
        return OrderItem(field=field, direction=direction)

    def asc(self, items: list) -> str:
        """ASC direction."""
        return "ASC"

    def desc(self, items: list) -> str:
        """DESC direction."""
        return "DESC"

    def limit_clause(self, items: list) -> int:
        """Extract integer from LIMIT clause."""
        for item in items:
            if isinstance(item, Token) and item.type == "INTEGER":
                return int(item)
        return int(items[-1])

    def group_clause(self, items: list) -> list[GroupKey]:
        """Extract GroupKeys from GROUP BY clause."""
        return [item for item in items if isinstance(item, GroupKey)]

    def group_time(self, items: list) -> GroupKey:
        """GROUP BY time bucket (day, week, month, year)."""
        return GroupKey(kind="time_bucket", value=str(items[0]).lower())

    def group_field(self, items: list) -> GroupKey:
        """GROUP BY field name."""
        return GroupKey(kind="field", value=str(items[0]))

    def time_bucket(self, items: list) -> str:
        """Time bucket keyword."""
        return str(items[0]).lower()

    # === Aggregations ===

    def agg_expr_list(self, items: list) -> list[AggExpr]:
        """List of aggregation expressions."""
        return list(items)

    def agg_expr(self, items: list) -> AggExpr:
        """Single aggregation expression like COUNT(*) or AVG(tss)."""
        func = str(items[0]).upper()
        field_or_star = items[1]
        if isinstance(field_or_star, Token) and field_or_star.type == "STAR":
            field = None
        else:
            field = str(field_or_star)
        return AggExpr(func=func, field=field)

    # === Expressions ===

    @v_args(inline=True)
    def or_expr(self, *items) -> Expr:
        """OR expression with left-associative tree building."""
        exprs = _filter_tokens(list(items))
        if len(exprs) == 1:
            return exprs[0]
        result = exprs[0]
        for item in exprs[1:]:
            result = BinaryOp(op="OR", left=result, right=item)
        return result

    @v_args(inline=True)
    def and_expr(self, *items) -> Expr:
        """AND expression with left-associative tree building."""
        exprs = _filter_tokens(list(items))
        if len(exprs) == 1:
            return exprs[0]
        result = exprs[0]
        for item in exprs[1:]:
            result = BinaryOp(op="AND", left=result, right=item)
        return result

    def not_op(self, items: list) -> NotOp:
        """NOT expression."""
        non_tokens = _filter_tokens(items)
        return NotOp(expr=non_tokens[0] if non_tokens else items[-1])

    def comparison(self, items: list) -> Comparison:
        """Field comparison (field op value)."""
        field = str(items[0])
        op = items[1]
        value = items[2]
        return Comparison(field=field, op=op, value=value)

    def eq(self, items: list) -> str:
        """Equals operator."""
        return "="

    def ne(self, items: list) -> str:
        """Not equals operator."""
        return "!="

    def gt(self, items: list) -> str:
        """Greater than operator."""
        return ">"

    def ge(self, items: list) -> str:
        """Greater than or equal operator."""
        return ">="

    def lt(self, items: list) -> str:
        """Less than operator."""
        return "<"

    def le(self, items: list) -> str:
        """Less than or equal operator."""
        return "<="

    def in_expr(self, items: list) -> InList:
        """IN or NOT IN expression."""
        field = str(items[0])
        negated = False
        values = []
        for item in items[1:]:
            if isinstance(item, Token) and item.type == "NOT_KW":
                negated = True
            elif isinstance(item, list):
                values = item
        return InList(field=field, values=values, negated=negated)

    def value_list(self, items: list) -> list[Value]:
        """Comma-separated list of values."""
        return list(items)

    def between_expr(self, items: list) -> Between:
        """BETWEEN expression."""
        field = str(items[0])
        values = _filter_tokens(items[1:])
        return Between(field=field, low=values[0], high=values[1])

    def null_check(self, items: list) -> NullCheck:
        """IS NULL or IS NOT NULL check."""
        field = str(items[0])
        is_null = True
        for item in items[1:]:
            if isinstance(item, Token) and item.type == "NOT_KW":
                is_null = False
        return NullCheck(field=field, is_null=is_null)

    def text_match(self, items: list) -> TextMatch:
        """Text matching (CONTAINS, STARTS WITH, ENDS WITH)."""
        field = str(items[0])
        op = items[1]
        value = items[2]
        if isinstance(value, StringValue):
            value = value.value
        return TextMatch(field=field, op=op, value=value)

    def contains(self, items: list) -> str:
        """CONTAINS operator."""
        return "CONTAINS"

    def starts_with(self, items: list) -> str:
        """STARTS WITH operator."""
        return "STARTS_WITH"

    def ends_with(self, items: list) -> str:
        """ENDS WITH operator."""
        return "ENDS_WITH"

    def boolean_field(self, items: list) -> BooleanField:
        """Standalone boolean field reference."""
        return BooleanField(field=str(items[0]))

    # === Values ===

    def number_value(self, items: list) -> NumberValue:
        """Numeric value with optional unit."""
        value = float(items[0])
        unit = str(items[1]).lower() if len(items) > 1 else None
        return NumberValue(value=value, unit=unit)

    def unit(self, items: list) -> str:
        """Unit suffix token."""
        return str(items[0]).lower()

    def string(self, items: list) -> StringValue:
        """String literal with quote handling."""
        raw = str(items[0])
        if raw.startswith('"'):
            value = raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        else:
            value = raw[1:-1].replace("\\'", "'").replace("\\\\", "\\")
        return StringValue(value=value)

    def date_value(self, items: list) -> DateValue:
        """Absolute date/datetime value."""
        date_str = str(items[0])
        if len(items) > 1:
            time_str = str(items[1])[1:]  # TIME token includes 'T' prefix
        else:
            time_str = "00:00:00"
        dt = datetime.fromisoformat(f"{date_str}T{time_str}")
        return DateValue(value=dt)

    def relative_date(self, items: list) -> RelativeDate:
        """Relative date expression like NOW - 30d."""
        base = str(items[0]).upper()
        offset_days = items[1] if len(items) > 1 else None
        return RelativeDate(base=base, offset_days=offset_days)

    def date_keyword(self, items: list) -> str:
        """Date keyword token (NOW, TODAY, START_OF_*)."""
        return str(items[0]).upper()

    def date_arith(self, items: list) -> int:
        """Date arithmetic (+ or - with number and unit)."""
        sign = 1 if str(items[0]) == "+" else -1
        amount = int(items[1])
        unit = str(items[2]).lower()

        days_per_unit = {
            "d": 1,
            "w": 7,
            "mo": 30,
            "y": 365,
        }
        return sign * amount * days_per_unit.get(unit, 1)

    def true(self, items: list) -> BoolValue:
        """Boolean true literal."""
        return BoolValue(value=True)

    def false(self, items: list) -> BoolValue:
        """Boolean false literal."""
        return BoolValue(value=False)

    def duration_value(self, items: list) -> DurationValue:
        """Duration in colon format (HH:MM:SS or MM:SS)."""
        parts = str(items[0]).split(":")
        if len(parts) == 2:
            minutes, seconds = int(parts[0]), int(parts[1])
            total = minutes * 60 + seconds
        else:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            total = hours * 3600 + minutes * 60 + seconds
        return DurationValue(seconds=total)

    # === Identifiers ===

    def field(self, items: list) -> str:
        """Field name identifier."""
        return str(items[0])
