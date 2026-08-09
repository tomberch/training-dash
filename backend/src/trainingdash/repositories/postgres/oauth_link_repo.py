"""PostgreSQL implementation of OAuthLinkRepo."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import UserOAuthLink


class PostgresOAuthLinkRepo:
    """PostgreSQL implementation of OAuthLinkRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_provider_id(self, provider: str, provider_user_id: str) -> UserOAuthLink | None:
        result = await self._db.execute(
            select(UserOAuthLink).where(
                UserOAuthLink.provider == provider,
                UserOAuthLink.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[UserOAuthLink]:
        result = await self._db.execute(select(UserOAuthLink).where(UserOAuthLink.user_id == user_id))
        return list(result.scalars().all())

    async def get_for_user(self, user_id: int, provider: str) -> UserOAuthLink | None:
        result = await self._db.execute(
            select(UserOAuthLink).where(
                UserOAuthLink.user_id == user_id,
                UserOAuthLink.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def save(
        self,
        user_id: int,
        provider: str,
        provider_user_id: str,
        provider_email: str | None = None,
    ) -> UserOAuthLink:
        # Check for existing link
        result = await self._db.execute(
            select(UserOAuthLink).where(
                UserOAuthLink.user_id == user_id,
                UserOAuthLink.provider == provider,
            )
        )
        link = result.scalar_one_or_none()

        if link is None:
            link = UserOAuthLink(
                user_id=user_id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=provider_email,
            )
            self._db.add(link)
        else:
            link.provider_user_id = provider_user_id
            link.provider_email = provider_email

        await self._db.commit()
        await self._db.refresh(link)
        return link

    async def delete(self, user_id: int, provider: str) -> bool:
        result = await self._db.execute(
            select(UserOAuthLink).where(
                UserOAuthLink.user_id == user_id,
                UserOAuthLink.provider == provider,
            )
        )
        link = result.scalar_one_or_none()
        if link is None:
            return False
        await self._db.delete(link)
        await self._db.commit()
        return True

    async def count_for_user(self, user_id: int) -> int:
        result = await self._db.execute(
            select(func.count()).select_from(UserOAuthLink).where(UserOAuthLink.user_id == user_id)
        )
        return result.scalar() or 0
