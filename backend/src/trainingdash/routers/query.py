"""Query API endpoint for executing DSL queries."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser, DbSession
from trainingdash.domain.query import (
    ParseError,
    ValidationError,
    parse,
    translate,
    validate,
)
from trainingdash.domain.query.executor import (
    GroupedResult,
    ListResult,
    QueryResult,
    ScalarResult,
    execute_query,
)

router = APIRouter(prefix="/api", tags=["query"])


class QueryRequest(BaseModel):
    """Request body for query execution."""

    query: str = Field(..., description="DSL query string", min_length=1)


class QueryErrorDetail(BaseModel):
    """Error details for query failures."""

    stage: str = Field(..., description="Stage where error occurred: parse, validation, execution")
    message: str = Field(..., description="Human-readable error message")
    line: int | None = Field(None, description="Line number where error occurred (1-based)")
    column: int | None = Field(None, description="Column number where error occurred (1-based)")
    field: str | None = Field(None, description="Field name that caused the error")
    suggestions: list[str] | None = Field(None, description="Suggested corrections")
    context: str | None = Field(None, description="Context snippet showing error location")


class QueryErrorResponse(BaseModel):
    """Response body for query errors."""

    error: QueryErrorDetail


class ListQueryResponse(BaseModel):
    """Response body for list query results."""

    type: str = "list"
    results: list[dict[str, Any]]
    total: int
    page: int
    per_page: int


class ScalarQueryResponse(BaseModel):
    """Response body for scalar aggregation results."""

    type: str = "scalar"
    results: dict[str, Any]


class GroupedQueryResponse(BaseModel):
    """Response body for grouped aggregation results."""

    type: str = "grouped"
    group_by: list[str]
    results: list[dict[str, Any]]


def _result_to_response(result: QueryResult) -> dict:
    """Convert a QueryResult to a response dict."""
    if isinstance(result, ListResult):
        return {
            "type": "list",
            "results": result.results,
            "total": result.total,
            "page": result.page,
            "per_page": result.per_page,
        }
    if isinstance(result, ScalarResult):
        return {
            "type": "scalar",
            "results": result.results,
        }
    if isinstance(result, GroupedResult):
        return {
            "type": "grouped",
            "group_by": result.group_by,
            "results": result.results,
        }
    raise ValueError(f"Unknown result type: {type(result)}")


@router.post(
    "/query",
    response_model=ListQueryResponse | ScalarQueryResponse | GroupedQueryResponse,
    responses={
        400: {"model": QueryErrorResponse, "description": "Parse or validation error"},
        500: {"model": QueryErrorResponse, "description": "Execution error"},
    },
)
async def execute_query_endpoint(
    request: QueryRequest,
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number (1-indexed, for list queries without LIMIT)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (for list queries without LIMIT)"),
):
    """Execute a DSL query and return results.

    The query is parsed, validated, translated to SQL, and executed against
    the database. Results are returned in a format appropriate for the query type:

    - **List queries** (e.g., `tss > 100`): Returns paginated activity results
    - **Scalar aggregations** (e.g., `COUNT(*)`): Returns computed values
    - **Grouped aggregations** (e.g., `COUNT(*) GROUP BY month`): Returns grouped results

    Query examples:
    - `tss > 100` - Activities with TSS > 100
    - `distance > 50km AND date >= START_OF_MONTH` - Long rides this month
    - `COUNT(*), AVG(tss) WHERE date >= START_OF_YEAR GROUP BY month` - Monthly stats
    """
    query_text = request.query.strip()

    # Stage 1: Parse
    try:
        parsed = parse(query_text)
    except ParseError as e:
        context = e.get_context(query_text) if hasattr(e, "get_context") else None
        # Filter out internal Lark tokens from suggestions and message
        token_map = {
            "EQUAL": "=",
            "MORETHAN": ">",
            "LESSTHAN": "<",
            "COMMA": ",",
            "LPAREN": "(",
            "RPAREN": ")",
        }

        # Clean up suggestions
        suggestions = None
        if hasattr(e, "expected") and e.expected:
            suggestions = []
            for s in e.expected:
                if s.startswith("__ANON"):
                    continue  # Skip anonymous tokens
                mapped = token_map.get(s, s)
                if mapped not in suggestions:
                    suggestions.append(mapped)

        # Clean up error message - replace internal tokens with user-friendly names
        message = e.message
        for internal, friendly in token_map.items():
            message = message.replace(internal, friendly)
        # Remove __ANON_* references from message
        import re

        message = re.sub(r",?\s*__ANON_\d+", "", message)
        message = re.sub(r"__ANON_\d+,?\s*", "", message)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "stage": "parse",
                    "message": message,
                    "line": e.line,
                    "column": e.column,
                    "suggestions": suggestions if suggestions else None,
                    "context": context,
                }
            },
        )

    # Stage 2: Validate
    try:
        validated = validate(parsed, now=datetime.now())
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "stage": "validation",
                    "message": e.message,
                    "field": e.field,
                    "suggestions": e.suggestions if e.suggestions else None,
                }
            },
        )

    # Stage 3: Translate
    try:
        translated = translate(validated, user_id=user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "stage": "translation",
                    "message": str(e),
                }
            },
        )

    # Stage 4: Execute
    try:
        result = await execute_query(db, translated, user.id, page, per_page)
        return _result_to_response(result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "stage": "execution",
                    "message": str(e),
                }
            },
        )
