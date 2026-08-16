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

import contextlib
import io
import logging
import os
import tempfile
import zipfile
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

    def upload_fit(self, fit_bytes: bytes) -> str:
        """Upload a FIT file to Garmin Connect. Returns the new activity ID."""
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
            logger.info("Garmin login successful for %s", email)
            return True
        except GarminMFARequired:
            # Re-raise our own exception
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
                logger.warning("Garmin rate limited: %s", e)
                raise GarminAPIError(
                    "Garmin is temporarily blocking requests from this IP. "
                    "Please wait 30-60 minutes before trying again."
                ) from e
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

                activities.append(
                    GarminActivity(
                        id=str(item.get("activityId", "")),
                        name=item.get("activityName", ""),
                        started_at=started_at,
                        activity_type=item.get("activityType", {}).get("typeKey", ""),
                        distance_m=item.get("distance", 0) or 0,
                        duration_s=item.get("duration", 0) or 0,
                    )
                )

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
            zip_data = self._client.download_activity(activity_id, dl_fmt=self._client.ActivityDownloadFormat.ORIGINAL)

            # Extract FIT from ZIP
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                # Find the FIT file in the ZIP
                fit_files = [n for n in zf.namelist() if n.lower().endswith(".fit")]
                if not fit_files:
                    raise GarminAPIError(f"No FIT file found in download for activity {activity_id}")
                return zf.read(fit_files[0])

        except GarminAPIError:
            raise
        except Exception as e:
            raise GarminAPIError(f"Failed to download FIT for activity {activity_id}: {e}") from e

    def upload_fit(self, fit_bytes: bytes) -> str:
        """
        Upload a FIT file to Garmin Connect.

        The garminconnect library's upload_activity() requires a file path,
        so we write the FIT bytes to a temporary file first.

        Args:
            fit_bytes: The FIT file bytes to upload

        Returns:
            The Garmin activity ID of the uploaded activity

        Raises:
            GarminAPIError: if upload fails
        """
        if not self._client:
            raise GarminAPIError("Not authenticated")

        if not fit_bytes:
            raise GarminAPIError("No FIT data provided for upload")

        try:
            # Write FIT bytes to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
                tmp.write(fit_bytes)
                tmp_path = tmp.name

            try:
                # Upload the FIT file using import_activity (better documented response)
                # import_activity treats it as an import, not a device sync
                result = self._client.import_activity(tmp_path)
                logger.info("Garmin import_activity response: %r", result)

                # Extract activity ID from response
                # import_activity can return different formats:
                # 1. {'status': 'uploaded', 'fileName': '...'} - success but no ID
                # 2. {'detailedImportResult': {'successes': [...], 'failures': [...]}}
                # 3. {'activityId': '...'} - direct ID
                if isinstance(result, dict):
                    # Format 1: Simple status response (import_activity typical response)
                    if result.get("status") == "uploaded":
                        logger.info("Uploaded FIT to Garmin successfully (no activity ID returned)")
                        # Return a placeholder - the upload worked but Garmin didn't return an ID
                        return "uploaded"
                    
                    # Format 2: Detailed import result
                    detailed = result.get("detailedImportResult", {})
                    successes = detailed.get("successes", [])
                    if successes:
                        activity_id = str(successes[0].get("internalId", ""))
                        if activity_id:
                            logger.info("Uploaded FIT to Garmin, activity ID: %s", activity_id)
                            return activity_id

                    # Check for failures - these include duplicates
                    failures = detailed.get("failures", [])
                    if failures:
                        # Extract failure messages
                        failure_messages = []
                        for f in failures:
                            msgs = f.get("messages", [])
                            for m in msgs:
                                content = m.get("content", "")
                                if content:
                                    failure_messages.append(content)
                        
                        if failure_messages:
                            combined = "; ".join(failure_messages)
                            # Check for common failure reasons
                            if "duplicate" in combined.lower():
                                raise GarminAPIError(f"Activity already exists in Garmin Connect: {combined}")
                            raise GarminAPIError(f"Garmin upload failed: {combined}")
                        else:
                            raise GarminAPIError("Garmin upload failed with unknown error")
                    
                    # Format 3: Direct activityId
                    if "activityId" in result:
                        activity_id = str(result["activityId"])
                        logger.info("Uploaded FIT to Garmin (alt format), activity ID: %s", activity_id)
                        return activity_id
                    
                    # Check for empty detailedImportResult (might indicate duplicate)
                    if detailed and not successes and not failures:
                        logger.warning("Garmin returned empty detailedImportResult: %r", detailed)
                        raise GarminAPIError("Garmin rejected upload - activity may already exist")

                logger.warning("Unexpected Garmin upload response format: %r", result)
                raise GarminAPIError(
                    "Garmin returned unexpected response format. "
                    "Check Garmin Connect to verify if the activity was uploaded."
                )

            finally:
                # Clean up temp file
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)

        except GarminAPIError:
            raise
        except Exception as e:
            raise GarminAPIError(f"Failed to upload FIT to Garmin: {e}") from e


# Default client factory - can be replaced in tests
_client_factory: type[GarminClient] = GarminClient


def set_garmin_client_factory(factory: type) -> None:
    """Set the Garmin client factory (for testing)."""
    global _client_factory
    _client_factory = factory


def get_garmin_client() -> GarminClient:
    """Get a new Garmin client instance."""
    return _client_factory()
