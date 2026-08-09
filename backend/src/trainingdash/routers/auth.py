"""Authentication endpoints: login, logout, register."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from trainingdash.auth import (
    CurrentUser,
    DbSession,
    LoginRequest,
    create_session_cookie,
    hash_password,
    verify_password,
)
from trainingdash.dependencies import UserRepoD
from trainingdash.repositories.postgres.models import AppSettings, User
from trainingdash.routers.serializers import user_response

router = APIRouter(prefix="/api", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(db: DbSession, user_repo: UserRepoD, request: RegisterRequest):
    """Register a new user. First user becomes admin automatically."""
    # Check if email already exists
    if await user_repo.exists_by_email(request.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Check if this is the first user
    user_count = await user_repo.count()
    is_first_user = user_count == 0

    # Check if approval is required (not for first user)
    is_approved = True
    if not is_first_user:
        settings_result = await db.execute(select(AppSettings).where(AppSettings.key == "require_approval"))
        setting = settings_result.scalar_one_or_none()
        if setting and setting.as_bool():
            is_approved = False

    # Create user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        is_admin=is_first_user,
        is_approved=is_approved,
    )
    user = await user_repo.save(user)

    # Auto-login the user
    cookie = create_session_cookie(user.id)
    response = JSONResponse(user_response(user))
    response.set_cookie("session", cookie, httponly=True, samesite="lax")
    return response


@router.post("/login")
async def login(user_repo: UserRepoD, request: LoginRequest):
    """Authenticate user and set session cookie."""
    user = await user_repo.get_by_email(request.email)
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    cookie = create_session_cookie(user.id)
    response = JSONResponse(user_response(user))
    response.set_cookie("session", cookie, httponly=True, samesite="lax")
    return response


@router.post("/logout")
async def logout(user: CurrentUser):
    """Log out the current user by clearing the session cookie."""
    response = JSONResponse({"success": True})
    response.delete_cookie("session")
    return response
