"""Xert API client for syncing activities.

Based on Xert Online API Version 1.5:
https://www.xertonline.com/API.html

Authentication:
  - OAuth2 password grant (xert_public client) for activity listing and XSS fetch
  - Web session (form login at /auth/login) for FIT file download

FIT download:
  The Xert OAuth API has no FIT download endpoint. FIT files are available at
  https://www.xertonline.com/activities/download/<activity_id> but require a
  web session cookie obtained via the HTML login form (POST /auth/login with
  username=, password=, _token= form fields).

  The Bearer token from the OAuth flow does NOT authenticate the download URL.

Session expiry detection:
  A stale session returns HTTP 200 with Content-Type: text/html instead of
  application/octet-stream. _is_fit_response() encapsulates that check; on a
  stale-session hit the client re-logs in once and retries.

XSS (training load):
  Xert Strain Score is fetched via GET /oauth/activity/<id> (no session_data,
  summary-only response ~1 KB). XSS lives at response["summary"]["xss"].
  Stored as Activity.training_load; overwritten by TSS once the user has a
  threshold configured.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


class XertAPIError(Exception):
    """Raised when Xert API returns an error."""


@dataclass
class XertActivity:
    """Represents an activity from Xert's activity list API."""

    id: str  # 'path' field from Xert API — used in download URL and detail endpoint
    name: str
    started_at: datetime
    activity_type: str
    description: str = ""


class XertClientProtocol(Protocol):
    """Protocol for Xert API client, allows mocking in tests."""

    async def login(self, username: str, password: str) -> None:
        """Authenticate with Xert (OAuth2 + web session)."""
        ...

    async def list_activities(
        self,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
    ) -> list[XertActivity]:
        """List activities within a date range."""
        ...

    async def download_fit(self, activity_id: str) -> bytes:
        """Download the raw FIT file for an activity via the web session."""
        ...

    async def get_xss(self, activity_id: str) -> float | None:
        """Return the Xert Strain Score for an activity (lightweight JSON call)."""
        ...

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        ...


@dataclass
class _OAuthSession:
    """
    Owns the OAuth2 Bearer token state for XertClient.

    Extracted as an internal seam so the OAuth2 logic is independently
    navigable from the web-session logic. The httpx.AsyncClient is passed
    in so both auth surfaces share the same connection pool.
    """

    BASE_URL = "https://www.xertonline.com"
    CLIENT_ID = "xert_public"
    CLIENT_SECRET = "xert_public"

    _client: httpx.AsyncClient = field(default=None, repr=False)
    _access_token: str | None = field(default=None)
    _refresh_token: str | None = field(default=None)
    _token_expires_at: float = field(default=0.0)

    async def login(self, username: str, password: str) -> None:
        """Obtain OAuth2 Bearer token via password grant."""
        try:
            response = await self._client.post(
                f"{self.BASE_URL}/oauth/token",
                auth=(self.CLIENT_ID, self.CLIENT_SECRET),
                data={
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                },
            )
            if response.status_code == 401:
                raise XertAPIError("Invalid Xert credentials")
            response.raise_for_status()
            data = response.json()

            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 604800)
            self._token_expires_at = time.time() + expires_in - 60

            if not self._access_token:
                raise XertAPIError("No access_token in Xert login response")

        except httpx.HTTPStatusError as e:
            raise XertAPIError(
                f"Xert OAuth login failed: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e

    async def refresh(self) -> None:
        """Refresh the OAuth2 Bearer token."""
        if not self._refresh_token:
            raise XertAPIError("No refresh token available")
        try:
            response = await self._client.post(
                f"{self.BASE_URL}/oauth/token",
                auth=(self.CLIENT_ID, self.CLIENT_SECRET),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 604800)
            self._token_expires_at = time.time() + expires_in - 60
        except httpx.HTTPStatusError as e:
            raise XertAPIError(
                f"Token refresh failed: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e

    def auth_headers(self) -> dict[str, str]:
        """Return Authorization header dict; raises if not authenticated."""
        if not self._access_token:
            raise XertAPIError("Not authenticated — call login() first")
        return {"Authorization": f"Bearer {self._access_token}"}

    async def ensure_valid_token(self) -> None:
        """Refresh the Bearer token if it has expired or is about to expire."""
        if time.time() >= self._token_expires_at and self._refresh_token:
            await self.refresh()


class XertClient:
    """
    Xert API client.

    Uses two authentication surfaces:
      1. OAuth2 password grant  — for list_activities() and get_xss()
         Managed by the internal _OAuthSession.
      2. Web session cookie     — for download_fit()
         The httpx cookie jar is maintained automatically.

    Both surfaces are established in login(). Credentials (_username,
    _password) are stored so download_fit() can re-establish the web
    session if it expires mid-sync.
    """

    BASE_URL = "https://www.xertonline.com"

    def __init__(self) -> None:
        # follow_redirects=True so the web login POST follows its redirect
        self._client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        self._oauth = _OAuthSession(_client=self._client)
        # Stored for web session re-login in download_fit() on session expiry
        self._username: str | None = None
        self._password: str | None = None

    # ------------------------------------------------------------------
    # Web session authentication
    # ------------------------------------------------------------------

    async def _web_login(self, username: str, password: str) -> None:
        """
        Establish a web session cookie by submitting the HTML login form.

        Xert uses Laravel. The form at / contains a hidden _token field
        (CSRF). We submit:
            POST /auth/login
            Content-Type: application/x-www-form-urlencoded
            Body: username=<u>&password=<p>&_token=<csrf>

        On success the server redirects to /my-fitness (or similar) and
        sets laravel_session in the cookie jar. The httpx client stores
        the cookie automatically for subsequent requests.
        """
        try:
            # Fetch home page to get the CSRF _token from the login form
            home = await self._client.get(f"{self.BASE_URL}/")
            home.raise_for_status()

            # Extract hidden _token from the login form HTML
            match = re.search(r'name="_token"\s+value="([^"]+)"', home.text)
            if not match:
                raise XertAPIError(
                    "Could not find CSRF _token on Xert login page"
                )
            form_token = match.group(1)

            # Submit the login form
            # Field name is 'username' (not 'email') as confirmed by the HTML form
            login_resp = await self._client.post(
                f"{self.BASE_URL}/auth/login",
                data={
                    "username": username,
                    "password": password,
                    "_token": form_token,
                },
                headers={
                    "Referer": f"{self.BASE_URL}/",
                    "Origin": self.BASE_URL,
                },
            )

            # Detect failure: still on /auth or /auth/login after redirects
            final_path = str(login_resp.url).replace(self.BASE_URL, "")
            if final_path.startswith("/auth"):
                raise XertAPIError(
                    "Xert web login failed — invalid credentials or CSRF mismatch"
                )

        except XertAPIError:
            raise
        except httpx.HTTPStatusError as e:
            raise XertAPIError(
                f"Xert web login HTTP error: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_fit_response(response: httpx.Response) -> bool:
        """
        Return True if the response contains a valid FIT file.

        The download URL returns application/octet-stream for a real FIT file.
        A stale web session returns HTTP 200 with Content-Type: text/html
        (the login page). We check the Content-Type header first, then fall
        back to the FIT magic bytes at offset 8-12 as a belt-and-suspenders
        guard.
        """
        content_type = response.headers.get("content-type", "")
        if "octet-stream" in content_type or "fit" in content_type.lower():
            return True
        return (
            len(response.content) > 12
            and response.content[8:12] == b".FIT"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def login(self, username: str, password: str) -> None:
        """
        Authenticate with Xert — establishes both OAuth2 token and web session.

        Credentials are stored so download_fit() can re-establish the web
        session if it expires mid-sync.
        """
        self._username = username
        self._password = password
        await self._oauth.login(username, password)
        await self._web_login(username, password)

    async def list_activities(
        self,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
    ) -> list[XertActivity]:
        """
        List activities within a date range via OAuth API.

        curl -X GET "https://www.xertonline.com/oauth/activity?from=<ts>&to=<ts>"
             -H "Authorization: Bearer <token>"
        """
        await self._oauth.ensure_valid_token()

        if to_timestamp is None:
            to_timestamp = int(time.time())
        if from_timestamp is None:
            from_timestamp = to_timestamp - (30 * 24 * 60 * 60)

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/oauth/activity",
                headers=self._oauth.auth_headers(),
                params={"from": from_timestamp, "to": to_timestamp},
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise XertAPIError(
                    "Xert API returned success=false for activity list"
                )

            activities = []
            for item in data.get("activities", []):
                start_date_obj = item.get("start_date", {})
                date_str = start_date_obj.get("date", "")
                try:
                    started_at = datetime.strptime(
                        date_str.split(".")[0], "%Y-%m-%d %H:%M:%S"
                    )
                except (ValueError, AttributeError):
                    started_at = datetime.utcnow()

                activities.append(
                    XertActivity(
                        id=item.get("path", ""),
                        name=item.get("name", ""),
                        started_at=started_at,
                        activity_type=item.get("activity_type", ""),
                        description=item.get("description", ""),
                    )
                )

            return activities

        except httpx.HTTPStatusError as e:
            raise XertAPIError(
                f"Failed to list activities: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e

    async def download_fit(self, activity_id: str) -> bytes:
        """
        Download the raw FIT file for an activity via the web session cookie.

        URL: GET https://www.xertonline.com/activities/download/<activity_id>
        Returns application/octet-stream on success.

        If the session has expired the server returns HTTP 200 with an HTML
        page (Content-Type: text/html). In that case the client re-establishes
        the web session once and retries. Raises XertAPIError on second failure.
        """
        if not activity_id:
            raise XertAPIError("No activity_id provided for FIT download")

        url = f"{self.BASE_URL}/activities/download/{activity_id}"

        for attempt in range(2):
            try:
                response = await self._client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise XertAPIError(
                    f"FIT download HTTP error for {activity_id}:"
                    f" {e.response.status_code}"
                ) from e
            except httpx.RequestError as e:
                raise XertAPIError(
                    f"FIT download connection error: {e}"
                ) from e

            if self._is_fit_response(response):
                return response.content

            # Session expired — server returned an HTML page instead of FIT bytes
            if attempt == 0:
                logger.warning(
                    "Xert FIT download returned HTML for activity %s — "
                    "re-establishing web session and retrying",
                    activity_id,
                )
                if not self._username or not self._password:
                    raise XertAPIError(
                        "Web session expired and no credentials stored for re-login"
                    )
                await self._web_login(self._username, self._password)
            else:
                raise XertAPIError(
                    f"Xert FIT download for {activity_id} returned HTML after"
                    " re-login — session could not be re-established"
                )

        # Unreachable — loop always returns or raises
        raise XertAPIError(f"FIT download failed for {activity_id}")

    async def get_xss(self, activity_id: str) -> float | None:
        """
        Fetch the Xert Strain Score for an activity via a lightweight JSON call.

        Uses GET /oauth/activity/<id> WITHOUT include_session_data. The server
        returns a summary-only response (~1 KB) where XSS lives at
        response["summary"]["xss"].

        Returns None if XSS is not available (e.g. indoor trainer with no power).
        """
        await self._oauth.ensure_valid_token()

        if not activity_id:
            return None

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/oauth/activity/{activity_id}",
                headers=self._oauth.auth_headers(),
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                return None

            return data.get("summary", {}).get("xss")

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning(
                "Failed to fetch XSS for activity %s: %s", activity_id, e
            )
            return None

    async def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        await self._client.aclose()


# Default client factory — can be replaced in tests
_client_factory: type[XertClient] = XertClient


def set_xert_client_factory(factory: type) -> None:
    """Set the Xert client factory (for testing)."""
    global _client_factory
    _client_factory = factory


def get_xert_client() -> XertClient:
    """Get a new Xert client instance."""
    return _client_factory()
