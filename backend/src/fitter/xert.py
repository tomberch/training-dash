"""Xert API client for syncing activities."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


class XertAPIError(Exception):
    """Raised when Xert API returns an error."""
    pass


@dataclass
class XertActivity:
    """Represents an activity from Xert's API."""
    id: str
    name: str
    started_at: datetime
    fit_url: str | None  # URL to download FIT file


class XertClientProtocol(Protocol):
    """Protocol for Xert API client, allows mocking in tests."""
    
    async def login(self, email: str, password: str) -> None:
        """Authenticate with Xert."""
        ...
    
    async def list_activities(self, since: datetime | None = None) -> list[XertActivity]:
        """List activities, optionally filtered by date."""
        ...
    
    async def download_fit(self, activity: XertActivity) -> bytes:
        """Download the FIT file for an activity."""
        ...
    
    async def close(self) -> None:
        """Close the client."""
        ...


class XertClient:
    """
    Real Xert API client.
    
    Note: The actual Xert API details (endpoints, auth flow, response shapes)
    depend on Xert's API documentation. This implementation is based on
    common patterns and may need adjustment once the actual API is researched.
    """
    
    BASE_URL = "https://www.xertonline.com/api"
    
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._token: str | None = None
    
    async def login(self, email: str, password: str) -> None:
        """Authenticate with Xert and store the session token."""
        try:
            response = await self._client.post(
                f"{self.BASE_URL}/auth/login",
                json={"email": email, "password": password},
            )
            response.raise_for_status()
            data = response.json()
            self._token = data.get("token") or data.get("access_token")
            if not self._token:
                raise XertAPIError("No token in login response")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise XertAPIError("Invalid Xert credentials") from e
            raise XertAPIError(f"Xert login failed: {e}") from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e
    
    def _auth_headers(self) -> dict[str, str]:
        if not self._token:
            raise XertAPIError("Not authenticated")
        return {"Authorization": f"Bearer {self._token}"}
    
    async def list_activities(self, since: datetime | None = None) -> list[XertActivity]:
        """List activities from Xert."""
        params = {}
        if since:
            params["since"] = since.isoformat()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/activities",
                headers=self._auth_headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            
            activities = []
            for item in data.get("activities", []):
                activities.append(XertActivity(
                    id=str(item["id"]),
                    name=item.get("name", ""),
                    started_at=datetime.fromisoformat(item["start_time"].replace("Z", "+00:00")),
                    fit_url=item.get("fit_file_url"),
                ))
            return activities
        except httpx.HTTPStatusError as e:
            raise XertAPIError(f"Failed to list activities: {e}") from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e
    
    async def download_fit(self, activity: XertActivity) -> bytes:
        """Download the FIT file for an activity."""
        if not activity.fit_url:
            raise XertAPIError(f"No FIT URL for activity {activity.id}")
        
        try:
            response = await self._client.get(
                activity.fit_url,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            raise XertAPIError(f"Failed to download FIT: {e}") from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e
    
    async def close(self) -> None:
        await self._client.aclose()


# Default client factory - can be replaced in tests
_client_factory: type[XertClient] = XertClient


def set_xert_client_factory(factory: type) -> None:
    """Set the Xert client factory (for testing)."""
    global _client_factory
    _client_factory = factory


def get_xert_client() -> XertClient:
    """Get a new Xert client instance."""
    return _client_factory()
