from datetime import datetime, timezone
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeSerializer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.config import settings
from trainingdash.repositories.postgres.db import async_session
from trainingdash.repositories.postgres.models import User

serializer = URLSafeSerializer(settings.secret_key, salt="session")


class LoginRequest(BaseModel):
    email: str
    password: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


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


async def get_admin_user(user: CurrentUser) -> User:
    """Dependency that requires the current user to be an admin."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]