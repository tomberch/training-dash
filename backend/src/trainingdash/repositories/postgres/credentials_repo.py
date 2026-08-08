"""PostgreSQL implementations of credentials repositories."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import GarminCredentials, XertCredentials


class PostgresXertCredentialsRepo:
    """PostgreSQL implementation of XertCredentialsRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_user_id(self, user_id: int) -> XertCredentials | None:
        result = await self._db.execute(
            select(XertCredentials).where(XertCredentials.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def exists(self, user_id: int) -> bool:
        result = await self._db.execute(
            select(XertCredentials.user_id).where(XertCredentials.user_id == user_id)
        )
        return result.scalar_one_or_none() is not None

    async def save(
        self,
        user_id: int,
        xert_email: str,
        encrypted_password: str,
        sync_since: datetime | None = None,
    ) -> XertCredentials:
        result = await self._db.execute(
            select(XertCredentials).where(XertCredentials.user_id == user_id)
        )
        creds = result.scalar_one_or_none()

        if creds is None:
            creds = XertCredentials(
                user_id=user_id,
                xert_email=xert_email,
                encrypted_password=encrypted_password,
                sync_since=sync_since,
            )
            self._db.add(creds)
        else:
            creds.xert_email = xert_email
            creds.encrypted_password = encrypted_password
            if sync_since is not None:
                creds.sync_since = sync_since

        await self._db.commit()
        await self._db.refresh(creds)
        return creds

    async def delete(self, user_id: int) -> bool:
        result = await self._db.execute(
            select(XertCredentials).where(XertCredentials.user_id == user_id)
        )
        creds = result.scalar_one_or_none()
        if creds is None:
            return False
        await self._db.delete(creds)
        await self._db.commit()
        return True


class PostgresGarminCredentialsRepo:
    """PostgreSQL implementation of GarminCredentialsRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_user_id(self, user_id: int) -> GarminCredentials | None:
        result = await self._db.execute(
            select(GarminCredentials).where(GarminCredentials.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def exists(self, user_id: int) -> bool:
        result = await self._db.execute(
            select(GarminCredentials.user_id).where(
                GarminCredentials.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def save(
        self,
        user_id: int,
        garmin_email: str,
        encrypted_password: str,
        sync_since: datetime | None = None,
    ) -> GarminCredentials:
        result = await self._db.execute(
            select(GarminCredentials).where(GarminCredentials.user_id == user_id)
        )
        creds = result.scalar_one_or_none()

        if creds is None:
            creds = GarminCredentials(
                user_id=user_id,
                garmin_email=garmin_email,
                encrypted_password=encrypted_password,
                sync_since=sync_since,
            )
            self._db.add(creds)
        else:
            creds.garmin_email = garmin_email
            creds.encrypted_password = encrypted_password
            if sync_since is not None:
                creds.sync_since = sync_since

        await self._db.commit()
        await self._db.refresh(creds)
        return creds

    async def delete(self, user_id: int) -> bool:
        result = await self._db.execute(
            select(GarminCredentials).where(GarminCredentials.user_id == user_id)
        )
        creds = result.scalar_one_or_none()
        if creds is None:
            return False
        await self._db.delete(creds)
        await self._db.commit()
        return True
