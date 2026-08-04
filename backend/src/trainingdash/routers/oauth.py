"""OAuth SSO routes for GitHub and Google login.

This module provides OAuth authentication via GitHub and Google using the
fastapi-sso library. It supports both login/registration flows and connecting
OAuth accounts to existing users from the Settings page.
"""

import os
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func

from fastapi_sso.sso.github import GithubSSO
from fastapi_sso.sso.google import GoogleSSO
from fastapi_sso.sso.base import SSOBase

from trainingdash.auth import create_session_cookie, verify_session_cookie, DbSession
from trainingdash.models import User, UserOAuthLink, AppSettings

router = APIRouter(prefix="/auth", tags=["OAuth"])

# Configuration from environment
_base_url = os.getenv("BASE_URL", "http://localhost:8000")
_allow_insecure = os.getenv("DEBUG", "false").lower() == "true"

# OAuth provider credentials
_github_client_id = os.getenv("GITHUB_CLIENT_ID", "")
_github_client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
_google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
_google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")


@dataclass
class OAuthUserInfo:
    """Normalized user info extracted from OAuth provider response."""

    provider_user_id: str
    email: str
    display_name: str | None
    avatar_url: str | None


def _get_github_sso(callback_path: str = "/auth/github/callback") -> GithubSSO:
    """Create GitHub SSO instance with current config.

    Args:
        callback_path: The callback URL path for OAuth redirect.

    Returns:
        Configured GithubSSO instance.
    """
    return GithubSSO(
        client_id=_github_client_id,
        client_secret=_github_client_secret,
        redirect_uri=f"{_base_url}{callback_path}",
        allow_insecure_http=_allow_insecure,
    )


def _get_google_sso(callback_path: str = "/auth/google/callback") -> GoogleSSO:
    """Create Google SSO instance with current config.

    Args:
        callback_path: The callback URL path for OAuth redirect.

    Returns:
        Configured GoogleSSO instance.
    """
    return GoogleSSO(
        client_id=_google_client_id,
        client_secret=_google_client_secret,
        redirect_uri=f"{_base_url}{callback_path}",
        allow_insecure_http=_allow_insecure,
    )


async def _verify_oauth_and_extract_user(
    sso: SSOBase,
    request: Request,
    provider: str,
) -> OAuthUserInfo:
    """Verify OAuth callback and extract normalized user info.

    Args:
        sso: The SSO provider instance.
        request: The incoming callback request.
        provider: Provider name for error messages.

    Returns:
        Normalized user info from the OAuth provider.

    Raises:
        HTTPException: If OAuth verification fails or no email is provided.
    """
    try:
        async with sso:
            openid = await sso.verify_and_process(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {e}")

    if not openid:
        raise HTTPException(
            status_code=400, detail=f"Failed to get user info from {provider}"
        )

    if not openid.email:
        raise HTTPException(
            status_code=400,
            detail=f"{provider} account has no email. Please add an email to your {provider} account.",
        )

    # Build display name (Google may have first/last name instead)
    display_name = openid.display_name
    if not display_name and hasattr(openid, "first_name"):
        first = getattr(openid, "first_name", "") or ""
        last = getattr(openid, "last_name", "") or ""
        display_name = f"{first} {last}".strip() or None

    return OAuthUserInfo(
        provider_user_id=openid.id,
        email=openid.email,
        display_name=display_name,
        avatar_url=openid.picture,
    )


async def _get_or_create_oauth_user(
    db: DbSession,
    provider: str,
    user_info: OAuthUserInfo,
) -> User:
    """Find user by OAuth link or email, or create new user.

    The lookup order is:
    1. Existing OAuth link (same provider + provider_user_id)
    2. Existing user with matching email (auto-link)
    3. Create new user

    Always upserts the OAuth link with latest provider data.

    Args:
        db: Database session.
        provider: OAuth provider name ('github' or 'google').
        user_info: Normalized user info from OAuth provider.

    Returns:
        The matched or newly created User.
    """
    user: User | None = None

    # 1. Check existing OAuth link
    link_result = await db.execute(
        select(UserOAuthLink).where(
            UserOAuthLink.provider == provider,
            UserOAuthLink.provider_user_id == user_info.provider_user_id,
        )
    )
    existing_link = link_result.scalar_one_or_none()

    if existing_link:
        # Found existing OAuth link - load that user
        user_result = await db.execute(
            select(User).where(User.id == existing_link.user_id)
        )
        user = user_result.scalar_one_or_none()

        # Update link with latest provider data
        existing_link.provider_email = user_info.email
        existing_link.display_name = user_info.display_name
        existing_link.avatar_url = user_info.avatar_url

    if not user:
        # 2. Check if email matches existing user (auto-link)
        user_result = await db.execute(
            select(User).where(User.email == user_info.email)
        )
        user = user_result.scalar_one_or_none()

    if not user:
        # 3. Create new user
        user = await _create_new_oauth_user(db, user_info)

    # 4. Upsert OAuth link (if not already updated above)
    if not existing_link:
        new_link = UserOAuthLink(
            user_id=user.id,
            provider=provider,
            provider_user_id=user_info.provider_user_id,
            provider_email=user_info.email,
            display_name=user_info.display_name,
            avatar_url=user_info.avatar_url,
        )
        db.add(new_link)

    await db.commit()
    await db.refresh(user)
    return user


async def _create_new_oauth_user(db: DbSession, user_info: OAuthUserInfo) -> User:
    """Create a new user from OAuth info.

    Handles first-user-becomes-admin logic and approval requirements.

    Args:
        db: Database session.
        user_info: Normalized user info from OAuth provider.

    Returns:
        The newly created User (not yet committed).
    """
    # Check if this is the first user (becomes admin)
    count_result = await db.execute(select(func.count()).select_from(User))
    user_count = count_result.scalar()
    is_first_user = user_count == 0

    # Check if approval is required
    is_approved = True
    if not is_first_user:
        settings_result = await db.execute(
            select(AppSettings).where(AppSettings.key == "require_approval")
        )
        setting = settings_result.scalar_one_or_none()
        if setting and setting.as_bool():
            is_approved = False

    user = User(
        email=user_info.email,
        password_hash=None,  # OAuth-only user, no password
        display_name=user_info.display_name,
        is_admin=is_first_user,
        is_approved=is_approved,
    )
    db.add(user)
    await db.flush()  # Get user.id
    return user


def _create_session_response(user: User, redirect_to: str = "/") -> RedirectResponse:
    """Create redirect response with session cookie.

    Args:
        user: The authenticated user.
        redirect_to: URL to redirect to after setting cookie.

    Returns:
        RedirectResponse with session cookie set.
    """
    cookie = create_session_cookie(user.id)
    response = RedirectResponse(url=redirect_to, status_code=status.HTTP_302_FOUND)
    response.set_cookie("session", cookie, httponly=True, samesite="lax")
    return response


async def _handle_oauth_connect(
    request: Request,
    db: DbSession,
    sso: SSOBase,
    provider: str,
) -> RedirectResponse:
    """Handle OAuth callback when connecting from Settings.

    This is used when a logged-in user wants to link an OAuth provider
    to their existing account.

    Args:
        request: The incoming callback request.
        db: Database session.
        sso: The SSO provider instance.
        provider: OAuth provider name.

    Returns:
        Redirect to Settings with success or error query param.
    """
    # Verify OAuth and extract user info
    try:
        async with sso:
            openid = await sso.verify_and_process(request)
    except Exception:
        return RedirectResponse(
            url="/settings?error=oauth_failed", status_code=status.HTTP_302_FOUND
        )

    if not openid or not openid.email:
        return RedirectResponse(
            url="/settings?error=no_email", status_code=status.HTTP_302_FOUND
        )

    # Get current user from session
    cookie = request.cookies.get("session")
    if not cookie:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    user_id = verify_session_cookie(cookie)
    if not user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # Check if this OAuth account is already linked to another user
    existing_link = await db.execute(
        select(UserOAuthLink).where(
            UserOAuthLink.provider == provider,
            UserOAuthLink.provider_user_id == openid.id,
        )
    )
    link = existing_link.scalar_one_or_none()
    if link and link.user_id != user_id:
        return RedirectResponse(
            url="/settings?error=already_linked", status_code=status.HTTP_302_FOUND
        )

    # Build display name
    display_name = openid.display_name
    if not display_name and hasattr(openid, "first_name"):
        first = getattr(openid, "first_name", "") or ""
        last = getattr(openid, "last_name", "") or ""
        display_name = f"{first} {last}".strip() or None

    # Upsert OAuth link for current user
    if link:
        link.provider_email = openid.email
        link.display_name = display_name
        link.avatar_url = openid.picture
    else:
        new_link = UserOAuthLink(
            user_id=user_id,
            provider=provider,
            provider_user_id=openid.id,
            provider_email=openid.email,
            display_name=display_name,
            avatar_url=openid.picture,
        )
        db.add(new_link)

    await db.commit()
    return RedirectResponse(
        url=f"/settings?success={provider}_connected", status_code=status.HTTP_302_FOUND
    )


# =============================================================================
# GitHub Routes
# =============================================================================


@router.get("/github")
async def github_login() -> RedirectResponse:
    """Initiate GitHub OAuth login flow.

    Redirects the user to GitHub's authorization page. After authorization,
    GitHub redirects back to /auth/github/callback.

    Returns:
        Redirect to GitHub authorization URL.

    Raises:
        HTTPException: If GitHub OAuth is not configured.
    """
    if not _github_client_id:
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured")

    github_sso = _get_github_sso()
    async with github_sso:
        return await github_sso.get_login_redirect()


@router.get("/github/callback")
async def github_callback(request: Request, db: DbSession) -> RedirectResponse:
    """Handle GitHub OAuth callback after user authorization.

    Verifies the OAuth response, finds or creates the user, and sets
    a session cookie.

    Args:
        request: The callback request from GitHub.
        db: Database session.

    Returns:
        Redirect to home page with session cookie.

    Raises:
        HTTPException: If OAuth verification fails or no email provided.
    """
    if not _github_client_id:
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured")

    github_sso = _get_github_sso()
    user_info = await _verify_oauth_and_extract_user(github_sso, request, "GitHub")

    user = await _get_or_create_oauth_user(db, "github", user_info)
    return _create_session_response(user)


@router.get("/github/connect")
async def github_connect() -> RedirectResponse:
    """Initiate GitHub OAuth to connect to existing account.

    Used from Settings page to link GitHub to an existing user account.
    Redirects back to /auth/github/connect/callback.

    Returns:
        Redirect to GitHub authorization URL.

    Raises:
        HTTPException: If GitHub OAuth is not configured.
    """
    if not _github_client_id:
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured")

    github_sso = _get_github_sso("/auth/github/connect/callback")
    async with github_sso:
        return await github_sso.get_login_redirect()


@router.get("/github/connect/callback")
async def github_connect_callback(
    request: Request, db: DbSession
) -> RedirectResponse:
    """Handle GitHub OAuth callback when connecting from Settings.

    Links the GitHub account to the currently logged-in user.

    Args:
        request: The callback request from GitHub.
        db: Database session.

    Returns:
        Redirect to Settings with success or error query param.
    """
    if not _github_client_id:
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured")

    github_sso = _get_github_sso("/auth/github/connect/callback")
    return await _handle_oauth_connect(request, db, github_sso, "github")


# =============================================================================
# Google Routes
# =============================================================================


@router.get("/google")
async def google_login() -> RedirectResponse:
    """Initiate Google OAuth login flow.

    Redirects the user to Google's authorization page. After authorization,
    Google redirects back to /auth/google/callback.

    Returns:
        Redirect to Google authorization URL.

    Raises:
        HTTPException: If Google OAuth is not configured.
    """
    if not _google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    google_sso = _get_google_sso()
    async with google_sso:
        return await google_sso.get_login_redirect(
            params={"prompt": "consent", "access_type": "offline"}
        )


@router.get("/google/callback")
async def google_callback(request: Request, db: DbSession) -> RedirectResponse:
    """Handle Google OAuth callback after user authorization.

    Verifies the OAuth response, finds or creates the user, and sets
    a session cookie.

    Args:
        request: The callback request from Google.
        db: Database session.

    Returns:
        Redirect to home page with session cookie.

    Raises:
        HTTPException: If OAuth verification fails or no email provided.
    """
    if not _google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    google_sso = _get_google_sso()
    user_info = await _verify_oauth_and_extract_user(google_sso, request, "Google")

    user = await _get_or_create_oauth_user(db, "google", user_info)
    return _create_session_response(user)


@router.get("/google/connect")
async def google_connect() -> RedirectResponse:
    """Initiate Google OAuth to connect to existing account.

    Used from Settings page to link Google to an existing user account.
    Redirects back to /auth/google/connect/callback.

    Returns:
        Redirect to Google authorization URL.

    Raises:
        HTTPException: If Google OAuth is not configured.
    """
    if not _google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    google_sso = _get_google_sso("/auth/google/connect/callback")
    async with google_sso:
        return await google_sso.get_login_redirect(
            params={"prompt": "consent", "access_type": "offline"}
        )


@router.get("/google/connect/callback")
async def google_connect_callback(
    request: Request, db: DbSession
) -> RedirectResponse:
    """Handle Google OAuth callback when connecting from Settings.

    Links the Google account to the currently logged-in user.

    Args:
        request: The callback request from Google.
        db: Database session.

    Returns:
        Redirect to Settings with success or error query param.
    """
    if not _google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    google_sso = _get_google_sso("/auth/google/connect/callback")
    return await _handle_oauth_connect(request, db, google_sso, "google")
