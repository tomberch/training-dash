"""PostgreSQL implementation of AppSettingsRepo."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import AppSettings


class PostgresAppSettingsRepo:
    """PostgreSQL implementation of AppSettingsRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get(self, key: str) -> str | None:
        result = await self._db.execute(select(AppSettings).where(AppSettings.key == key))
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    async def get_bool(self, key: str, default: bool = False) -> bool:
        value = await self.get(key)
        if value is None:
            return default
        return AppSettings.str_to_bool(value)

    async def set(self, key: str, value: str) -> None:
        result = await self._db.execute(select(AppSettings).where(AppSettings.key == key))
        setting = result.scalar_one_or_none()

        if setting is None:
            setting = AppSettings(key=key, value=value)
            self._db.add(setting)
        else:
            setting.value = value

        await self._db.commit()

    async def list_all(self) -> list[AppSettings]:
        result = await self._db.execute(select(AppSettings))
        return list(result.scalars().all())
