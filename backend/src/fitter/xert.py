"""Xert API client for syncing activities.

Based on Xert Online API Version 1.4:
https://www.xertonline.com/API.html

Authentication: OAuth2 password grant with public client credentials.
Activity list: GET /oauth/activity?from=<timestamp>&to=<timestamp>
Activity details: GET /oauth/activity/<path>?include_session_data=1
FIT download: GET /activities/download/<path> (requires auth)
FIT upload: POST /oauth/upload (multipart/form-data)
"""

import logging
import time
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
    id: str  # 'path' field from Xert API - used for download URL
    name: str
    started_at: datetime
    activity_type: str
    description: str = ""


class XertClientProtocol(Protocol):
    """Protocol for Xert API client, allows mocking in tests."""
    
    async def login(self, username: str, password: str) -> None:
        """Authenticate with Xert using OAuth2 password grant."""
        ...
    
    async def list_activities(
        self, 
        from_timestamp: int | None = None, 
        to_timestamp: int | None = None
    ) -> list[XertActivity]:
        """List activities within a date range."""
        ...
    
    async def download_fit(self, activity: XertActivity) -> bytes:
        """Download the FIT file for an activity."""
        ...
    
    async def close(self) -> None:
        """Close the client."""
        ...


class XertClient:
    """
    Real Xert API client based on Xert Online API v1.4.
    
    Authentication uses OAuth2 password grant with public client credentials:
    - client_id: xert_public
    - client_secret: xert_public
    
    Tokens expire after 604800 seconds (7 days) and can be refreshed.
    """
    
    BASE_URL = "https://www.xertonline.com"
    CLIENT_ID = "xert_public"
    CLIENT_SECRET = "xert_public"
    
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=60.0)
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float = 0
    
    async def login(self, username: str, password: str) -> None:
        """
        Authenticate with Xert using OAuth2 password grant.
        
        curl -u xert_public:xert_public -POST "https://www.xertonline.com/oauth/token" 
             -d 'grant_type=password' -d 'username=...' -d 'password=...'
        """
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
            self._token_expires_at = time.time() + expires_in - 60  # 60s buffer
            
            if not self._access_token:
                raise XertAPIError("No access_token in login response")
                
        except httpx.HTTPStatusError as e:
            raise XertAPIError(f"Xert login failed: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e
    
    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the refresh token."""
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
            raise XertAPIError(f"Token refresh failed: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e
    
    def _auth_headers(self) -> dict[str, str]:
        if not self._access_token:
            raise XertAPIError("Not authenticated")
        return {"Authorization": f"Bearer {self._access_token}"}
    
    async def _ensure_valid_token(self) -> None:
        """Refresh token if expired or about to expire."""
        if time.time() >= self._token_expires_at and self._refresh_token:
            await self._refresh_access_token()
    
    async def list_activities(
        self, 
        from_timestamp: int | None = None, 
        to_timestamp: int | None = None
    ) -> list[XertActivity]:
        """
        List activities within a date range.
        
        curl -X GET "https://www.xertonline.com/oauth/activity?from=<ts>&to=<ts>" 
             -H "Authorization: Bearer <token>"
        
        Args:
            from_timestamp: Unix timestamp for start of range (required by API)
            to_timestamp: Unix timestamp for end of range (required by API)
        
        Returns:
            List of XertActivity objects with id (path) for FIT download
        """
        await self._ensure_valid_token()
        
        # Default to last 30 days if not specified
        if to_timestamp is None:
            to_timestamp = int(time.time())
        if from_timestamp is None:
            from_timestamp = to_timestamp - (30 * 24 * 60 * 60)
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/oauth/activity",
                headers=self._auth_headers(),
                params={
                    "from": from_timestamp,
                    "to": to_timestamp,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("success"):
                raise XertAPIError("Xert API returned success=false")
            
            activities = []
            for item in data.get("activities", []):
                # Parse start_date object: {"date": "2017-08-12 11:08:29.000000", "timezone_type": 3, "timezone": "UTC"}
                start_date_obj = item.get("start_date", {})
                date_str = start_date_obj.get("date", "")
                
                if date_str:
                    # Parse "2017-08-12 11:08:29.000000" format
                    try:
                        started_at = datetime.strptime(date_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        started_at = datetime.now()
                else:
                    started_at = datetime.now()
                
                # The 'path' field is used for download URL: /activities/download/<path>
                activities.append(XertActivity(
                    id=item.get("path", ""),
                    name=item.get("name", ""),
                    started_at=started_at,
                    activity_type=item.get("activity_type", ""),
                    description=item.get("description", ""),
                ))
            
            return activities
            
        except httpx.HTTPStatusError as e:
            raise XertAPIError(f"Failed to list activities: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise XertAPIError(f"Failed to connect to Xert: {e}") from e
    
    async def download_fit(self, activity: XertActivity) -> bytes:
        """
        Download the FIT file for an activity.
        
        URL format: https://www.xertonline.com/activities/download/<path>
        Where <path> is the activity's 'path' field from list_activities.
        """
        await self._ensure_valid_token()
        
        if not activity.id:
            raise XertAPIError(f"No activity path/id for download")
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/activities/download/{activity.id}",
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            return response.content
            
        except httpx.HTTPStatusError as e:
            raise XertAPIError(f"Failed to download FIT: HTTP {e.response.status_code}") from e
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
