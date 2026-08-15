"""AST validator that normalizes field names, converts units, and resolves dates.

The validator transforms a raw parsed AST into a normalized form ready for
SQL translation. It:
1. Resolves field aliases to internal names
2. Converts units to internal units
3. Resolves relative dates to absolute datetimes
4. Validates operator/type compatibility
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

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
from .fields import (
    AGGREGATABLE_FIELDS,
    FieldType,
    get_conversion_factor,
    get_field_def,
    is_text_match_valid,
    is_valid_operator,
    resolve_field_name,
    suggest_field_name,
)


class ValidationError(Exception):
    """Error during query validation with context."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        suggestions: list[str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.field = field
        self.suggestions = suggestions or []

    def __str__(self) -> str:
        msg = self.message
        if self.suggestions:
            msg += f" Did you mean: {', '.join(repr(s) for s in self.suggestions)}?"
        return msg


@dataclass
class ValidatedQuery:
    """A validated and normalized query ready for translation."""

    type: str  # "list" or "aggregate"
    projection: Projection | None
    conditions: Expr | None
    group_by: list[GroupKey] | None
    order_by: list[OrderItem] | None
    limit: int | None


class QueryValidator:
    """Validates and normalizes parsed query AST."""

    def __init__(self, now: datetime | None = None):
        """Initialize the validator.

        Args:
            now: Current datetime for resolving relative dates. Defaults to datetime.now().
        """
        self._now = now or datetime.now()

    def validate(self, query: Query) -> ValidatedQuery:
        """Validate and normalize a parsed query.

        Args:
            query: The parsed query AST

        Returns:
            A ValidatedQuery with normalized field names and values

        Raises:
            ValidationError: If the query has semantic errors
        """
        # Validate and normalize projection
        projection = self._validate_projection(query.projection, query.type)

        # Validate and normalize conditions
        conditions = self._validate_expr(query.conditions) if query.conditions else None

        # Validate and normalize GROUP BY
        group_by = self._validate_group_by(query.group_by) if query.group_by else None

        # Validate and normalize ORDER BY
        order_by = self._validate_order_by(query.order_by) if query.order_by else None

        # Validate limit
        if query.limit is not None and query.limit < 0:
            raise ValidationError("LIMIT must be non-negative")

        return ValidatedQuery(
            type=query.type,
            projection=projection,
            conditions=conditions,
            group_by=group_by,
            order_by=order_by,
            limit=query.limit,
        )

    def _validate_projection(self, projection: Projection | None, query_type: str) -> Projection | None:
        """Validate the projection clause."""
        if projection is None:
            return None

        if projection.kind == "fields" and projection.fields:
            # Validate each field name
            normalized_fields = []
            for field in projection.fields:
                internal = resolve_field_name(field)
                if not internal:
                    suggestions = suggest_field_name(field)
                    raise ValidationError(
                        f"Unknown field: '{field}'",
                        field=field,
                        suggestions=suggestions,
                    )
                normalized_fields.append(internal)
            return replace(projection, fields=normalized_fields)

        if projection.kind == "aggregates" and projection.aggregates:
            # Validate each aggregation
            normalized_aggs = []
            for agg in projection.aggregates:
                normalized_aggs.append(self._validate_agg_expr(agg))
            return replace(projection, aggregates=normalized_aggs)

        return projection

    def _validate_agg_expr(self, agg: AggExpr) -> AggExpr:
        """Validate an aggregation expression."""
        if agg.field is None:
            # COUNT(*) is always valid
            if agg.func != "COUNT":
                raise ValidationError(f"{agg.func}(*) is not valid. Only COUNT(*) is allowed.")
            return agg

        # Validate the field
        internal = resolve_field_name(agg.field)
        if not internal:
            suggestions = suggest_field_name(agg.field)
            raise ValidationError(
                f"Unknown field: '{agg.field}'",
                field=agg.field,
                suggestions=suggestions,
            )

        # Check if field is aggregatable
        if internal not in AGGREGATABLE_FIELDS:
            raise ValidationError(
                f"Field '{agg.field}' cannot be used in {agg.func}(). Only numeric fields can be aggregated."
            )

        return replace(agg, field=internal)

    def _validate_group_by(self, group_by: list[GroupKey]) -> list[GroupKey]:
        """Validate GROUP BY keys."""
        normalized = []
        for key in group_by:
            if key.kind == "field":
                internal = resolve_field_name(key.value)
                if not internal:
                    suggestions = suggest_field_name(key.value)
                    raise ValidationError(
                        f"Unknown field: '{key.value}'",
                        field=key.value,
                        suggestions=suggestions,
                    )
                normalized.append(replace(key, value=internal))
            else:
                # Time bucket - already validated by grammar
                normalized.append(key)
        return normalized

    def _validate_order_by(self, order_by: list[OrderItem]) -> list[OrderItem]:
        """Validate ORDER BY items."""
        normalized = []
        for item in order_by:
            internal = resolve_field_name(item.field)
            if not internal:
                suggestions = suggest_field_name(item.field)
                raise ValidationError(
                    f"Unknown field: '{item.field}'",
                    field=item.field,
                    suggestions=suggestions,
                )
            normalized.append(replace(item, field=internal))
        return normalized

    def _validate_expr(self, expr: Expr) -> Expr:
        """Validate and normalize an expression."""
        if isinstance(expr, BinaryOp):
            return replace(
                expr,
                left=self._validate_expr(expr.left),
                right=self._validate_expr(expr.right),
            )

        if isinstance(expr, NotOp):
            return replace(expr, expr=self._validate_expr(expr.expr))

        if isinstance(expr, Comparison):
            return self._validate_comparison(expr)

        if isinstance(expr, Between):
            return self._validate_between(expr)

        if isinstance(expr, InList):
            return self._validate_in_list(expr)

        if isinstance(expr, NullCheck):
            return self._validate_null_check(expr)

        if isinstance(expr, TextMatch):
            return self._validate_text_match(expr)

        if isinstance(expr, BooleanField):
            return self._validate_boolean_field(expr)

        return expr

    def _validate_comparison(self, comp: Comparison) -> Comparison:
        """Validate a comparison expression."""
        # Resolve field name
        internal = resolve_field_name(comp.field)
        if not internal:
            suggestions = suggest_field_name(comp.field)
            raise ValidationError(
                f"Unknown field: '{comp.field}'",
                field=comp.field,
                suggestions=suggestions,
            )

        # Get field definition
        field_def = get_field_def(internal)
        if not field_def:
            raise ValidationError(f"Field '{internal}' has no definition")

        # Validate operator for field type
        if not is_valid_operator(field_def.field_type, comp.op):
            raise ValidationError(
                f"Operator '{comp.op}' is not valid for field '{comp.field}' (type: {field_def.field_type.value})"
            )

        # Normalize the value
        normalized_value = self._normalize_value(comp.value, field_def, comp.field)

        return replace(comp, field=internal, value=normalized_value)

    def _validate_between(self, between: Between) -> Between:
        """Validate a BETWEEN expression."""
        # Resolve field name
        internal = resolve_field_name(between.field)
        if not internal:
            suggestions = suggest_field_name(between.field)
            raise ValidationError(
                f"Unknown field: '{between.field}'",
                field=between.field,
                suggestions=suggestions,
            )

        field_def = get_field_def(internal)
        if not field_def:
            raise ValidationError(f"Field '{internal}' has no definition")

        # BETWEEN only makes sense for comparable types
        if field_def.field_type not in (
            FieldType.NUMBER,
            FieldType.DATE,
            FieldType.DURATION,
        ):
            raise ValidationError(
                f"BETWEEN is not valid for field '{between.field}' (type: {field_def.field_type.value})"
            )

        # Normalize the values
        low = self._normalize_value(between.low, field_def, between.field)
        high = self._normalize_value(between.high, field_def, between.field)

        return replace(between, field=internal, low=low, high=high)

    def _validate_in_list(self, in_list: InList) -> InList:
        """Validate an IN expression."""
        # Resolve field name
        internal = resolve_field_name(in_list.field)
        if not internal:
            suggestions = suggest_field_name(in_list.field)
            raise ValidationError(
                f"Unknown field: '{in_list.field}'",
                field=in_list.field,
                suggestions=suggestions,
            )

        field_def = get_field_def(internal)
        if not field_def:
            raise ValidationError(f"Field '{internal}' has no definition")

        # Normalize all values
        normalized_values = [self._normalize_value(v, field_def, in_list.field) for v in in_list.values]

        return replace(in_list, field=internal, values=normalized_values)

    def _validate_null_check(self, null_check: NullCheck) -> NullCheck:
        """Validate an IS NULL / IS NOT NULL expression."""
        internal = resolve_field_name(null_check.field)
        if not internal:
            suggestions = suggest_field_name(null_check.field)
            raise ValidationError(
                f"Unknown field: '{null_check.field}'",
                field=null_check.field,
                suggestions=suggestions,
            )

        field_def = get_field_def(internal)
        if not field_def:
            raise ValidationError(f"Field '{internal}' has no definition")

        # Warn if checking nullable on non-nullable field
        if not field_def.nullable and null_check.is_null:
            raise ValidationError(f"Field '{null_check.field}' is never NULL")

        return replace(null_check, field=internal)

    def _validate_text_match(self, text_match: TextMatch) -> TextMatch:
        """Validate a text matching expression."""
        internal = resolve_field_name(text_match.field)
        if not internal:
            suggestions = suggest_field_name(text_match.field)
            raise ValidationError(
                f"Unknown field: '{text_match.field}'",
                field=text_match.field,
                suggestions=suggestions,
            )

        field_def = get_field_def(internal)
        if not field_def:
            raise ValidationError(f"Field '{internal}' has no definition")

        # Text match only works on string fields
        if not is_text_match_valid(field_def.field_type):
            raise ValidationError(
                f"Text matching ({text_match.op}) is not valid for field "
                f"'{text_match.field}' (type: {field_def.field_type.value}). "
                "Only string fields support text matching."
            )

        return replace(text_match, field=internal)

    def _validate_boolean_field(self, bool_field: BooleanField) -> BooleanField:
        """Validate a standalone boolean field reference."""
        internal = resolve_field_name(bool_field.field)
        if not internal:
            suggestions = suggest_field_name(bool_field.field)
            raise ValidationError(
                f"Unknown field: '{bool_field.field}'",
                field=bool_field.field,
                suggestions=suggestions,
            )

        field_def = get_field_def(internal)
        if not field_def:
            raise ValidationError(f"Field '{internal}' has no definition")

        # Standalone field reference only works for boolean fields
        if field_def.field_type != FieldType.BOOLEAN:
            raise ValidationError(
                f"Field '{bool_field.field}' is not a boolean field. "
                f"Use '{bool_field.field} = true' or '{bool_field.field} = false' instead."
            )

        return replace(bool_field, field=internal)

    def _normalize_value(self, value: Value, field_def, field_name: str) -> Value:
        """Normalize a value for a field, converting units and resolving dates."""
        if isinstance(value, NumberValue):
            return self._normalize_number(value, field_def, field_name)

        if isinstance(value, DurationValue):
            return self._normalize_duration(value, field_def, field_name)

        if isinstance(value, RelativeDate):
            return self._resolve_relative_date(value, field_def, field_name)

        if isinstance(value, DateValue):
            # Validate field expects a date
            if field_def.field_type != FieldType.DATE:
                raise ValidationError(
                    f"Date value not valid for field '{field_name}' (type: {field_def.field_type.value})"
                )
            return value

        if isinstance(value, StringValue):
            if field_def.field_type != FieldType.STRING:
                raise ValidationError(
                    f"String value not valid for field '{field_name}' (type: {field_def.field_type.value})"
                )
            return value

        if isinstance(value, BoolValue):
            if field_def.field_type != FieldType.BOOLEAN:
                raise ValidationError(
                    f"Boolean value not valid for field '{field_name}' (type: {field_def.field_type.value})"
                )
            return value

        return value

    def _normalize_number(self, value: NumberValue, field_def, field_name: str) -> NumberValue:
        """Normalize a number value, converting units if needed."""
        # Check field type compatibility
        if field_def.field_type not in (FieldType.NUMBER, FieldType.DURATION):
            raise ValidationError(
                f"Numeric value not valid for field '{field_name}' (type: {field_def.field_type.value})"
            )

        if value.unit is None:
            # No unit specified, use as-is
            return value

        if field_def.internal_unit is None:
            # Field has no unit, but value has unit - warn
            raise ValidationError(f"Field '{field_name}' does not accept units, but got value with unit '{value.unit}'")

        # Convert unit
        factor = get_conversion_factor(value.unit, field_def.internal_unit)
        if factor is None:
            raise ValidationError(
                f"Cannot convert unit '{value.unit}' to '{field_def.internal_unit}' for field '{field_name}'"
            )

        converted_value = value.value * factor
        return NumberValue(value=converted_value, unit=None)

    def _normalize_duration(self, value: DurationValue, field_def, field_name: str) -> NumberValue:
        """Normalize a duration value (colon format) to a number in seconds."""
        if field_def.field_type != FieldType.DURATION:
            raise ValidationError(
                f"Duration value not valid for field '{field_name}' (type: {field_def.field_type.value})"
            )

        # Duration is already in seconds, convert to NumberValue
        return NumberValue(value=float(value.seconds), unit=None)

    def _resolve_relative_date(self, value: RelativeDate, field_def, field_name: str) -> DateValue:
        """Resolve a relative date to an absolute datetime."""
        if field_def.field_type != FieldType.DATE:
            raise ValidationError(f"Date value not valid for field '{field_name}' (type: {field_def.field_type.value})")

        # Calculate base datetime
        base_dt = self._get_base_datetime(value.base)

        # Apply offset if present
        if value.offset_days is not None:
            base_dt = base_dt + timedelta(days=value.offset_days)

        return DateValue(value=base_dt)

    def _get_base_datetime(self, base: str) -> datetime:
        """Get the base datetime for a relative date keyword."""
        now = self._now

        if base == "NOW":
            return now

        if base == "TODAY":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)

        if base == "START_OF_DAY":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)

        if base == "START_OF_WEEK":
            # Monday is weekday 0
            days_since_monday = now.weekday()
            start = now - timedelta(days=days_since_monday)
            return start.replace(hour=0, minute=0, second=0, microsecond=0)

        if base == "START_OF_MONTH":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if base == "START_OF_YEAR":
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        raise ValidationError(f"Unknown date keyword: '{base}'")


def validate(query: Query, now: datetime | None = None) -> ValidatedQuery:
    """Validate and normalize a parsed query.

    Convenience function that creates a QueryValidator and validates the query.

    Args:
        query: The parsed query AST
        now: Current datetime for resolving relative dates

    Returns:
        A ValidatedQuery with normalized field names and values

    Raises:
        ValidationError: If the query has semantic errors
    """
    validator = QueryValidator(now=now)
    return validator.validate(query)
