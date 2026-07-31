from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fitter.config import settings
from fitter.db import async_session
from fitter.models import User

serializer = URLSafeSerializer(settings.secret_key, salt="session")


def create_session_cookie(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id, "ts": datetime.now(timezone.utc).isoformat()})


def verify_session_cookie(cookie: str) -> int | None:
    try:
        data = serializer.loads(cookie)
        return data["user_id"]
    except (BadSignature, KeyError):
        return None


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(request: Request, db: DbSession) -> User:
    cookie = request.cookies.get("session")
    if not cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = verify_session_cookie(cookie)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]