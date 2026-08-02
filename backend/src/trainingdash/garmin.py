"""Garmin Connect API client for syncing activities.

Uses the garminconnect library which authenticates via mobile SSO flow
(same as the official Garmin Connect Android app).

MFA Support:
- First login attempt may trigger MFA requirement
- Two-step flow: login() returns mfa_required=True, then complete_mfa(code)
- After MFA completion, tokens are obtained and stored

Activity sync:
- list_activities() returns activities in a date range
- download_fit() downloads original FIT file for an activity
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from garminconnect import Garmin

logger = logging.getLogger(__name__)


class GarminAPIError(Exception):
    """Raised when Garmin API returns an error."""
    pass


class GarminMFARequired(Exception):
    """Raised when MFA is required to complete login."""
    pass


@dataclass
class GarminActivity:
    """Represents an activity from Garmin Connect."""
    id: str  # activityId from Garmin
    name: str
    started_at: datetime
    activity_type: str
    distance_m: float
    duration_s: float


class GarminClientProtocol(Protocol):
    """Protocol for Garmin API client, allows mocking in tests."""

    def login(self, email: str, password: str) -> bool:
        """
        Authenticate with Garmin Connect.
        Returns True if logged in, raises GarminMFARequired if MFA needed.
        """
        ...

    def complete_mfa(self, code: str) -> None:
        """Complete MFA authentication with the provided code."""
        ...

    def list_activities(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[GarminActivity]:
        """List activities within a date range."""
        ...

    def download_fit(self, activity_id: str) -> bytes:
        """Download the original FIT file for an activity."""
        ...


class GarminClient:
    """
    Garmin Connect API client wrapper.

    Handles the two-step MFA flow:
    1. login() attempts authentication, may raise GarminMFARequired
    2. complete_mfa() finishes authentication with MFA code
    """

    def __init__(self):
        self._client: Garmin | None = None
        self._email: str | None = None
        self._password: str | None = None
        self._mfa_code: str | None = None
        self._awaiting_mfa: bool = False

    def _mfa_callback(self) -> str:
        """Callback for garminconnect library when MFA is required."""
        if self._mfa_code:
            return self._mfa_code
        # Signal that MFA is required but not yet provided
        self._awaiting_mfa = True
        raise GarminMFARequired("MFA code required")

    def login(self, email: str, password: str) -> bool:
        """
        Authenticate with Garmin Connect.

        Returns:
            True if login successful without MFA

        Raises:
            GarminMFARequired: if MFA is required (call complete_mfa next)
            GarminAPIError: if login fails for other reasons
        """
        self._email = email
        self._password = password
        self._awaiting_mfa = False
        self._mfa_code = None

        try:
            self._client = Garmin(
                email=email,
                password=password,
                prompt_mfa=self._mfa_callback,
            )
            self._client.login()
            return True
        except GarminMFARequired:
            # Re-raise our own exception
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "mfa" in error_msg or "two-factor" in error_msg or "verification" in error_msg:
                self._awaiting_mfa = True
                raise GarminMFARequired("MFA code required") from e
            if "credentials" in error_msg or "password" in error_msg or "invalid" in error_msg:
                raise GarminAPIError("Invalid Garmin credentials") from e
            raise GarminAPIError(f"Garmin login failed: {e}") from e

    def complete_mfa(self, code: str) -> None:
        """
        Complete MFA authentication with the provided code.

        Args:
            code: The MFA code from authenticator app or email

        Raises:
            GarminAPIError: if MFA completion fails
        """
        if not self._awaiting_mfa:
            raise GarminAPIError("No MFA in progress")
        if not self._email or not self._password:
            raise GarminAPIError("Must call login() before complete_mfa()")

        self._mfa_code = code

        try:
            self._client = Garmin(
                email=self._email,
                password=self._password,
                prompt_mfa=self._mfa_callback,
            )
            self._client.login()
            self._awaiting_mfa = False
        except GarminMFARequired:
            raise GarminAPIError("Invalid MFA code") from None
        except Exception as e:
            error_msg = str(e).lower()
            if "mfa" in error_msg or "code" in error_msg or "invalid" in error_msg:
                raise GarminAPIError("Invalid MFA code") from e
            raise GarminAPIError(f"Garmin MFA failed: {e}") from e

    def list_activities(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[GarminActivity]:
        """
        List activities within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of GarminActivity objects
        """
        if not self._client:
            raise GarminAPIError("Not authenticated")

        try:
            # garminconnect uses date strings in format "YYYY-MM-DD"
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            # Get activities - the library returns a list of dicts
            raw_activities = self._client.get_activities_by_date(start_str, end_str)

            activities = []
            for item in raw_activities:
                # Parse startTimeLocal: "2024-01-15 10:30:00"
                start_time_str = item.get("startTimeLocal", "")
                if start_time_str:
                    try:
                        started_at = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        started_at = datetime.now()
                else:
                    started_at = datetime.now()

                activities.append(GarminActivity(
                    id=str(item.get("activityId", "")),
                    name=item.get("activityName", ""),
                    started_at=started_at,
                    activity_type=item.get("activityType", {}).get("typeKey", ""),
                    distance_m=item.get("distance", 0) or 0,
                    duration_s=item.get("duration", 0) or 0,
                ))

            return activities

        except Exception as e:
            raise GarminAPIError(f"Failed to list activities: {e}") from e

    def download_fit(self, activity_id: str) -> bytes:
        """
        Download the original FIT file for an activity.

        Args:
            activity_id: The Garmin activity ID

        Returns:
            FIT file bytes
        """
        if not self._client:
            raise GarminAPIError("Not authenticated")

        try:
            # download_activity returns ZIP bytes containing the FIT file
            zip_data = self._client.download_activity(
                activity_id,
                dl_fmt=self._client.ActivityDownloadFormat.ORIGINAL
            )
            
            # Extract FIT from ZIP
            import io
            import zipfile
            
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                # Find the FIT file in the ZIP
                fit_files = [n for n in zf.namelist() if n.lower().endswith('.fit')]
                if not fit_files:
                    raise GarminAPIError(f"No FIT file found in download for activity {activity_id}")
                return zf.read(fit_files[0])

        except GarminAPIError:
            raise
        except Exception as e:
            raise GarminAPIError(f"Failed to download FIT for activity {activity_id}: {e}") from e


# Default client factory - can be replaced in tests
_client_factory: type[GarminClient] = GarminClient


def set_garmin_client_factory(factory: type) -> None:
    """Set the Garmin client factory (for testing)."""
    global _client_factory
    _client_factory = factory


def get_garmin_client() -> GarminClient:
    """Get a new Garmin client instance."""
    return _client_factory()
