"""Xert API client for syncing activities.

Based on Xert Online API Version 1.4:
https://www.xertonline.com/API.html

Authentication: OAuth2 password grant with public client credentials.
Activity list: GET /oauth/activity?from=<timestamp>&to=<timestamp>
Activity details: GET /oauth/activity/<path>?include_session_data=1
FIT upload: POST /oauth/upload (multipart/form-data)

Note: The Xert API does NOT provide a FIT file download endpoint.
Activity data must be retrieved via the session_data JSON endpoint.
This is the same approach used by Golden Cheetah's Xert integration.
"""

import logging
import time
from dataclasses import dataclass, field
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
    id: str  # 'path' field from Xert API
    name: str
    started_at: datetime
    activity_type: str
    description: str = ""


@dataclass
class XertSessionDataPoint:
    """A single data point from Xert session_data."""
    unix_time: int  # milliseconds
    power: float | None = None
    hr: int | None = None
    cad: float | None = None
    alt: float | None = None
    spd: float | None = None  # m/s * 1000
    dist: float | None = None  # meters
    lat: float | None = None
    lng: float | None = None
    mpa: float | None = None  # Maximum Power Available
    tws: float | None = None  # Total Work Score


@dataclass
class XertActivityDetail:
    """Full activity detail including session data from Xert API."""
    id: str
    name: str
    description: str
    started_at: datetime
    activity_type: str
    duration: float  # seconds
    distance: float  # km
    session_data: list[XertSessionDataPoint] = field(default_factory=list)
    # Xert training metrics (their equivalent to TSS)
    xss: float | None = None  # Xert Strain Score (total - like TSS)
    xlss: float | None = None  # Low Strain Score (endurance)
    xhss: float | None = None  # High Strain Score (threshold)
    xpss: float | None = None  # Peak Strain Score (anaerobic)
    focus: str | None = None  # e.g. "Rouleur", "Climber"
    difficulty: float | None = None
    difficulty_rating: str | None = None  # e.g. "5 - Hard"


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
    
    async def get_activity_detail(
        self, 
        activity: XertActivity,
        include_session_data: bool = True
    ) -> XertActivityDetail:
        """Get full activity detail including session data."""
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
    
    async def get_activity_detail(
        self, 
        activity: XertActivity,
        include_session_data: bool = True
    ) -> XertActivityDetail:
        """
        Get full activity detail including session data.
        
        This is how Golden Cheetah retrieves Xert activity data - there is no
        FIT download endpoint in the Xert OAuth API. The session_data contains
        per-second samples that can be converted to a FIT file or ingested directly.
        
        curl -X GET "https://www.xertonline.com/oauth/activity/<path>?include_session_data=1"
             -H "Authorization: Bearer <token>"
        """
        await self._ensure_valid_token()
        
        if not activity.id:
            raise XertAPIError("No activity path/id for detail request")
        
        try:
            params = {}
            if include_session_data:
                params["include_session_data"] = "1"
            
            response = await self._client.get(
                f"{self.BASE_URL}/oauth/activity/{activity.id}",
                headers=self._auth_headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("success"):
                raise XertAPIError("Xert API returned success=false for activity detail")
            
            # Parse summary data
            summary = data.get("summary", {})
            
            # Parse start_date
            start_date_obj = summary.get("start_date", {})
            date_str = start_date_obj.get("date", "")
            if date_str:
                try:
                    started_at = datetime.strptime(date_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    started_at = activity.started_at
            else:
                started_at = activity.started_at
            
            # Parse session_data samples
            session_data = []
            for point in data.get("session_data", []):
                session_data.append(XertSessionDataPoint(
                    unix_time=int(point.get("unix_time", 0)),
                    power=point.get("power"),
                    hr=point.get("hr"),
                    cad=point.get("cad"),
                    alt=point.get("alt"),
                    spd=point.get("spd"),
                    dist=point.get("dist"),
                    lat=point.get("lat"),
                    lng=point.get("lng"),
                    mpa=point.get("mpa"),
                    tws=point.get("tws"),
                ))
            
            return XertActivityDetail(
                id=activity.id,
                name=data.get("name", activity.name),
                description=data.get("description", ""),
                started_at=started_at,
                activity_type=summary.get("activity_type", activity.activity_type),
                duration=summary.get("duration", 0),
                distance=summary.get("distance", 0),
                session_data=session_data,
                # Xert training metrics
                xss=summary.get("xss"),
                xlss=summary.get("xlss"),
                xhss=summary.get("xhss"),
                xpss=summary.get("xpss"),
                focus=summary.get("focus"),
                difficulty=summary.get("difficulty"),
                difficulty_rating=summary.get("difficulty_rating"),
            )
            
        except httpx.HTTPStatusError as e:
            raise XertAPIError(f"Failed to get activity detail: HTTP {e.response.status_code}") from e
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
