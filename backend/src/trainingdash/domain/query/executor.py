"""Query executor that runs translated queries against the database.

The executor takes a TranslatedQuery and executes it against the database,
returning typed results appropriate for each query type.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Activity
from trainingdash.routers.datetime_utils import utc_str
from trainingdash.routers.serializers import activity_summary

from .translator import GroupedAggResult, ListQueryResult, ScalarAggResult, TranslatedQuery


@dataclass
class ListResult:
    """Result of a list query."""

    type: str = "list"
    results: list[dict] = None
    total: int = 0
    page: int = 1
    per_page: int = 20

    def __post_init__(self):
        if self.results is None:
            self.results = []


@dataclass
class ScalarResult:
    """Result of a scalar aggregation (no GROUP BY)."""

    type: str = "scalar"
    results: dict = None

    def __post_init__(self):
        if self.results is None:
            self.results = {}


@dataclass
class GroupedResult:
    """Result of a grouped aggregation."""

    type: str = "grouped"
    group_by: list[str] = None
    results: list[dict] = None

    def __post_init__(self):
        if self.group_by is None:
            self.group_by = []
        if self.results is None:
            self.results = []


QueryResult = ListResult | ScalarResult | GroupedResult


class QueryExecutor:
    """Executes translated queries against the database."""

    def __init__(self, db: AsyncSession):
        """Initialize the executor.

        Args:
            db: The database session to use for queries.
        """
        self._db = db

    async def execute(
        self,
        translated: TranslatedQuery,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> QueryResult:
        """Execute a translated query.

        Args:
            translated: The translated query from the translator
            user_id: The user ID for pagination counting
            page: Page number for list queries without LIMIT
            per_page: Items per page for list queries without LIMIT

        Returns:
            A QueryResult appropriate for the query type
        """
        if isinstance(translated, ListQueryResult):
            return await self._execute_list(translated, user_id, page, per_page)
        if isinstance(translated, ScalarAggResult):
            return await self._execute_scalar(translated)
        if isinstance(translated, GroupedAggResult):
            return await self._execute_grouped(translated)
        raise ValueError(f"Unknown translated query type: {type(translated)}")

    async def _execute_list(
        self,
        translated: ListQueryResult,
        user_id: int,
        page: int,
        per_page: int,
    ) -> ListResult:
        """Execute a list query."""
        query = translated.query

        if translated.has_explicit_limit:
            # User specified LIMIT, use it directly without pagination
            result = await self._db.execute(query)
            activities = list(result.scalars().all())

            return ListResult(
                results=[activity_summary(a) for a in activities],
                total=len(activities),
                page=1,
                per_page=len(activities),
            )
        else:
            # No LIMIT, apply server-side pagination
            # First get total count (need a separate count query)
            count_query = select(func.count()).select_from(Activity).where(Activity.user_id == user_id)
            # Apply the same WHERE conditions from the original query
            # We need to extract them - for now, execute count against full set
            # The translated query already has user_id filter, so we can count from it
            # Actually we need to build a proper count - let's do it differently

            # Get the count by re-executing with count
            # For simplicity, we'll execute the full query and count in-memory for now
            # TODO: optimize with proper count query
            count_result = await self._db.execute(query.with_only_columns(func.count()).order_by(None))
            total = count_result.scalar_one()

            # Apply pagination
            offset = (page - 1) * per_page
            paginated_query = query.limit(per_page).offset(offset)

            result = await self._db.execute(paginated_query)
            activities = list(result.scalars().all())

            return ListResult(
                results=[activity_summary(a) for a in activities],
                total=total,
                page=page,
                per_page=per_page,
            )

    async def _execute_scalar(self, translated: ScalarAggResult) -> ScalarResult:
        """Execute a scalar aggregation query."""
        result = await self._db.execute(translated.query)
        row = result.one()

        # Convert row to dict using column labels
        results = {}
        for i, col in enumerate(translated.query.selected_columns):
            label = col.name if hasattr(col, "name") else str(col)
            value = row[i]
            # Format the value appropriately
            if isinstance(value, float):
                value = round(value, 2)
            results[label] = value

        return ScalarResult(results=results)

    async def _execute_grouped(self, translated: GroupedAggResult) -> GroupedResult:
        """Execute a grouped aggregation query."""
        result = await self._db.execute(translated.query)
        rows = result.all()

        # Convert rows to list of dicts
        results = []
        columns = translated.query.selected_columns
        column_names = [col.name if hasattr(col, "name") else str(col) for col in columns]

        for row in rows:
            row_dict = {}
            for i, name in enumerate(column_names):
                value = row[i]
                # Format datetime values
                if isinstance(value, datetime):
                    value = utc_str(value)
                elif isinstance(value, float):
                    value = round(value, 2)
                row_dict[name] = value
            results.append(row_dict)

        return GroupedResult(
            group_by=translated.group_columns,
            results=results,
        )


async def execute_query(
    db: AsyncSession,
    translated: TranslatedQuery,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
) -> QueryResult:
    """Execute a translated query.

    Convenience function that creates a QueryExecutor and executes.

    Args:
        db: The database session
        translated: The translated query from the translator
        user_id: The user ID for pagination counting
        page: Page number for list queries
        per_page: Items per page for list queries

    Returns:
        A QueryResult appropriate for the query type
    """
    executor = QueryExecutor(db)
    return await executor.execute(translated, user_id, page, per_page)
