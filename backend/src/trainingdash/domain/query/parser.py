"""Query DSL parser using Lark."""

from pathlib import Path

from lark import Lark, UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from .ast import Query
from .transformer import QueryTransformer


class ParseError(Exception):
    """Error during query parsing with position information."""

    def __init__(
        self,
        message: str,
        line: int = 1,
        column: int = 1,
        expected: list[str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.expected = expected or []

    def get_context(self, query: str, context_chars: int = 30) -> str:
        """Get a context snippet showing where the error occurred."""
        lines = query.split("\n")
        if self.line <= len(lines):
            error_line = lines[self.line - 1]
            # Build pointer
            pointer = " " * (self.column - 1) + "^"
            return f"{error_line}\n{pointer}"
        return query


# Load grammar from file
_grammar_path = Path(__file__).parent / "grammar.lark"
_grammar = _grammar_path.read_text()

# Create parser instance (cached)
_parser = Lark(
    _grammar,
    parser="lalr",
    transformer=QueryTransformer(),
    propagate_positions=True,
)


def parse(query: str) -> Query:
    """Parse a query string into an AST.

    Args:
        query: The query string to parse

    Returns:
        A Query AST node

    Raises:
        ParseError: If the query has syntax errors
    """
    if not query or not query.strip():
        raise ParseError("Empty query", line=1, column=1)

    try:
        result = _parser.parse(query)
        if not isinstance(result, Query):
            raise ParseError(f"Unexpected parse result type: {type(result)}")
        return result
    except UnexpectedToken as e:
        expected = list(e.expected) if e.expected else []
        # Make expected tokens more readable
        readable_expected = _make_expected_readable(expected)
        message = f"Unexpected token: {e.token}"
        if readable_expected:
            message += f". Expected: {', '.join(readable_expected)}"
        raise ParseError(
            message=message,
            line=e.line,
            column=e.column,
            expected=readable_expected,
        ) from e
    except UnexpectedCharacters as e:
        message = f"Unexpected character: '{e.char}'"
        raise ParseError(
            message=message,
            line=e.line,
            column=e.column,
        ) from e
    except UnexpectedInput as e:
        raise ParseError(
            message=str(e),
            line=getattr(e, "line", 1),
            column=getattr(e, "column", 1),
        ) from e


def _make_expected_readable(expected: list[str]) -> list[str]:
    """Convert internal token names to readable descriptions."""
    token_descriptions = {
        "IDENTIFIER": "field name",
        "NUMBER": "number",
        "INTEGER": "integer",
        "DOUBLE_QUOTED_STRING": "string",
        "SINGLE_QUOTED_STRING": "string",
        "DATE": "date (YYYY-MM-DD)",
        "STAR": "*",
        "AND_KW": "AND",
        "OR_KW": "OR",
        "NOT_KW": "NOT",
        "WHERE_KW": "WHERE",
        "SELECT_KW": "SELECT",
        "ORDER_KW": "ORDER",
        "BY_KW": "BY",
        "GROUP_KW": "GROUP",
        "LIMIT_KW": "LIMIT",
        "ASC_KW": "ASC",
        "DESC_KW": "DESC",
        "IN_KW": "IN",
        "BETWEEN_KW": "BETWEEN",
        "IS_KW": "IS",
        "NULL_KW": "NULL",
        "CONTAINS_KW": "CONTAINS",
        "STARTS_KW": "STARTS",
        "ENDS_KW": "ENDS",
        "WITH_KW": "WITH",
        "NOW_KW": "NOW",
        "TODAY_KW": "TODAY",
        "TRUE_KW": "true",
        "FALSE_KW": "false",
        "COUNT_KW": "COUNT",
        "SUM_KW": "SUM",
        "AVG_KW": "AVG",
        "MIN_KW": "MIN",
        "MAX_KW": "MAX",
        "LPAR": "(",
        "RPAR": ")",
        "COMMA": ",",
        "EQ": "=",
        "NE": "!=",
        "GT": ">",
        "GE": ">=",
        "LT": "<",
        "LE": "<=",
    }

    readable = []
    seen = set()
    for token in expected:
        desc = token_descriptions.get(token, token)
        if desc not in seen:
            readable.append(desc)
            seen.add(desc)
    return readable
