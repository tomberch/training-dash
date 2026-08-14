"""PostgreSQL implementation of SavedFilterRepo."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.query import ParseError, ValidationError, parse, validate
from trainingdash.repositories.postgres.models import SavedFilter


class QueryValidationError(Exception):
    """Raised when a saved filter query fails validation."""

    def __init__(self, message: str, stage: str = "validation"):
        self.message = message
        self.stage = stage
        super().__init__(message)


def _validate_query(query_text: str) -> None:
    """Validate a query string. Raises QueryValidationError on failure."""
    try:
        parsed = parse(query_text)
    except ParseError as e:
        raise QueryValidationError(e.message, stage="parse")

    try:
        validate(parsed, now=datetime.now())
    except ValidationError as e:
        raise QueryValidationError(e.message, stage="validation")


class PostgresSavedFilterRepo:
    """PostgreSQL implementation of SavedFilterRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, filter_id: int, user_id: int) -> SavedFilter | None:
        result = await self._db.execute(
            select(SavedFilter).where(
                SavedFilter.id == filter_id,
                SavedFilter.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, user_id: int) -> SavedFilter | None:
        result = await self._db.execute(
            select(SavedFilter).where(
                SavedFilter.name == name,
                SavedFilter.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[SavedFilter]:
        result = await self._db.execute(
            select(SavedFilter)
            .where(SavedFilter.user_id == user_id)
            .order_by(SavedFilter.name)
        )
        return list(result.scalars().all())

    async def get_default(self, user_id: int) -> SavedFilter | None:
        result = await self._db.execute(
            select(SavedFilter).where(
                SavedFilter.user_id == user_id,
                SavedFilter.is_default == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        name: str,
        query_text: str,
        description: str | None = None,
        is_default: bool = False,
    ) -> SavedFilter:
        # Validate the query
        _validate_query(query_text)

        # If this is being set as default, clear existing defaults
        if is_default:
            await self._clear_default_internal(user_id)

        filter_obj = SavedFilter(
            user_id=user_id,
            name=name,
            query_text=query_text,
            description=description,
            is_default=is_default,
        )
        self._db.add(filter_obj)
        await self._db.commit()
        await self._db.refresh(filter_obj)
        return filter_obj

    async def update(
        self,
        filter_id: int,
        user_id: int,
        name: str | None = None,
        query_text: str | None = None,
        description: str | None = None,
        is_default: bool | None = None,
    ) -> SavedFilter | None:
        filter_obj = await self.get_by_id(filter_id, user_id)
        if filter_obj is None:
            return None

        # Validate new query if provided
        if query_text is not None:
            _validate_query(query_text)
            filter_obj.query_text = query_text

        if name is not None:
            filter_obj.name = name

        if description is not None:
            filter_obj.description = description

        if is_default is not None:
            if is_default and not filter_obj.is_default:
                # Setting as default - clear others first
                await self._clear_default_internal(user_id)
            filter_obj.is_default = is_default

        await self._db.commit()
        await self._db.refresh(filter_obj)
        return filter_obj

    async def delete(self, filter_id: int, user_id: int) -> bool:
        filter_obj = await self.get_by_id(filter_id, user_id)
        if filter_obj is None:
            return False

        await self._db.delete(filter_obj)
        await self._db.commit()
        return True

    async def set_default(self, filter_id: int, user_id: int) -> bool:
        filter_obj = await self.get_by_id(filter_id, user_id)
        if filter_obj is None:
            return False

        # Clear existing defaults
        await self._clear_default_internal(user_id)

        # Set this one as default
        filter_obj.is_default = True
        await self._db.commit()
        return True

    async def clear_default(self, user_id: int) -> None:
        await self._clear_default_internal(user_id)
        await self._db.commit()

    async def _clear_default_internal(self, user_id: int) -> None:
        """Clear default flag without committing (for internal use)."""
        await self._db.execute(
            update(SavedFilter)
            .where(
                SavedFilter.user_id == user_id,
                SavedFilter.is_default == True,  # noqa: E712
            )
            .values(is_default=False)
        )
