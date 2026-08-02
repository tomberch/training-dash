"""Authentication endpoints: login, logout."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from trainingdash.auth import (
    CurrentUser,
    DbSession,
    LoginRequest,
    create_session_cookie,
    verify_password,
)
from trainingdash.models import User

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
async def login(db: DbSession, request: LoginRequest):
    """Authenticate user and set session cookie."""
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    cookie = create_session_cookie(user.id)
    response = JSONResponse(
        {"user_id": user.id, "username": user.username, "is_admin": user.is_admin}
    )
    response.set_cookie("session", cookie, httponly=True, samesite="lax")
    return response


@router.post("/logout")
async def logout(user: CurrentUser):
    """Log out the current user by clearing the session cookie."""
    response = JSONResponse({"success": True})
    response.delete_cookie("session")
    return response
