"""Mock Garmin client for E2E testing.

This module provides a mock GarminClient that returns pre-configured activities
and FIT files from the E2E fixtures directory. It is activated by setting
the environment variable MOCK_GARMIN_ENABLED=true.

FIT files are read from MOCK_GARMIN_FIXTURES_DIR (default: /app/e2e-fixtures/fit-files).
The mock returns activities based on the FIT files present in that directory.

Usage in docker-compose.e2e.yml:
    environment:
      MOCK_GARMIN_ENABLED: "true"
      MOCK_GARMIN_FIXTURES_DIR: /app/e2e-fixtures/fit-files
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from trainingdash.integrations.garmin.client import (
    GarminActivity,
    GarminAPIError,
    _mask_email,
)

logger = logging.getLogger(__name__)

# Default fixtures directory (matches docker-compose.e2e.yml volume mount)
DEFAULT_FIXTURES_DIR = "/app/e2e-fixtures/fit-files"

# Sentinel password value that makes the mock simulate failed credentials.
# Not a real secret — used only by the E2E mock to exercise the failure path.
INVALID_PASSWORD_SENTINEL = "invalid"  # noqa: S105 - not a secret, E2E mock sentinel


class MockGarminClient:
    """
    Mock Garmin client for E2E testing.

    Returns activities based on FIT files in the fixtures directory.
    Each FIT file becomes an activity with a predictable ID derived from filename.
    """

    def __init__(self):
        self._fixtures_dir = Path(os.environ.get("MOCK_GARMIN_FIXTURES_DIR", DEFAULT_FIXTURES_DIR))
        self._logged_in = False
        self._email: str | None = None
        logger.info("MockGarminClient initialized with fixtures_dir=%r", self._fixtures_dir)

    def login(self, email: str, password: str) -> bool:
        """Simulate Garmin login. Always succeeds unless password is the invalid sentinel."""
        if password == INVALID_PASSWORD_SENTINEL:
            raise GarminAPIError("Invalid Garmin credentials")
        self._logged_in = True
        self._email = email
        # Security: use %r (repr) to escape special characters and truncate to prevent log injection
        # Email is masked to avoid PII exposure
        masked = _mask_email(email)
        logger.info("MockGarminClient: login successful for %r", masked[:50])
        return True

    def complete_mfa(self, code: str) -> None:
        """Simulate MFA completion. Mock always succeeds."""
        logger.info("MockGarminClient: MFA completed")

    def list_activities(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[GarminActivity]:
        """
        Return activities based on FIT files in the fixtures directory.

        Each .fit file becomes an activity. Activity IDs are derived from
        the filename (e.g., 'cp-ride1-2min.fit' -> 'garmin-cp-ride1-2min').
        """
        if not self._fixtures_dir.exists():
            logger.warning(
                "MockGarminClient: fixtures directory does not exist: %r",
                self._fixtures_dir,
            )
            return []

        activities = []
        fit_files = sorted(self._fixtures_dir.glob("*.fit"))

        # Generate activities with staggered timestamps
        base_time = datetime.now() - timedelta(days=len(fit_files))

        for i, fit_path in enumerate(fit_files):
            base_id = fit_path.stem  # filename without extension
            activity_id = f"garmin-{base_id}"  # Prefix to distinguish from Xert
            started_at = base_time + timedelta(days=i, hours=8)

            activities.append(
                GarminActivity(
                    id=activity_id,
                    name=f"Mock Garmin: {base_id.replace('-', ' ').title()}",
                    started_at=started_at,
                    activity_type="cycling",
                    distance_m=25000.0 + i * 1000,  # 25km base + 1km per activity
                    duration_s=3600.0 + i * 300,  # 1hr base + 5min per activity
                )
            )

        logger.info("MockGarminClient: list_activities returning %d activities", len(activities))
        return activities

    def download_fit(self, activity_id: str) -> bytes:
        """
        Return FIT file bytes for the given activity ID.

        The activity_id should be prefixed with 'garmin-' and the rest matches
        a filename (without extension) in the fixtures directory.
        """
        # Strip 'garmin-' prefix if present
        base_id = activity_id
        if activity_id.startswith("garmin-"):
            base_id = activity_id[7:]

        fit_path = self._fixtures_dir / f"{base_id}.fit"

        if not fit_path.exists():
            raise GarminAPIError(f"FIT file not found for activity: {activity_id}")

        logger.info("MockGarminClient: download_fit returning %r", fit_path)
        return fit_path.read_bytes()

    def upload_fit(self, fit_bytes: bytes) -> str:
        """
        Simulate FIT file upload to Garmin Connect.

        Returns a mock activity ID based on current timestamp.
        In E2E tests, this allows verifying the upload flow without actually
        hitting Garmin's servers.
        """
        import time

        # Generate a predictable mock activity ID
        timestamp = int(time.time())
        mock_activity_id = f"mock-garmin-upload-{timestamp}"

        logger.info(
            "MockGarminClient: upload_fit(%d bytes) -> %r",
            len(fit_bytes),
            mock_activity_id,
        )
        return mock_activity_id


def is_mock_enabled() -> bool:
    """Check if Garmin mock is enabled via environment variable."""
    return os.environ.get("MOCK_GARMIN_ENABLED", "").lower() in ("true", "1", "yes")


def setup_mock_garmin_client() -> None:
    """
    Configure the Garmin client factory to use MockGarminClient if enabled.

    Call this at application startup (e.g., in app.py or a startup event).
    """
    if is_mock_enabled():
        from trainingdash.integrations.garmin import set_garmin_client_factory

        set_garmin_client_factory(MockGarminClient)
        logger.info("Garmin mock client enabled for E2E testing")
