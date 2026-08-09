"""Mock Xert client for E2E testing.

This module provides a mock XertClient that returns pre-configured activities
and FIT files from the E2E fixtures directory. It is activated by setting
the environment variable MOCK_XERT_ENABLED=true.

FIT files are read from MOCK_XERT_FIXTURES_DIR (default: /app/e2e-fixtures/fit-files).
The mock returns activities based on the FIT files present in that directory.

Usage in docker-compose.e2e.yml:
    environment:
      MOCK_XERT_ENABLED: "true"
      MOCK_XERT_FIXTURES_DIR: /app/e2e-fixtures/fit-files
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from trainingdash.integrations.xert.client import XertActivity, XertAPIError

logger = logging.getLogger(__name__)

# Default fixtures directory (matches docker-compose.e2e.yml volume mount)
DEFAULT_FIXTURES_DIR = "/app/e2e-fixtures/fit-files"

# Mock XSS values for test activities (Xert Strain Score)
MOCK_XSS_VALUES = {
    "cp-ride1-2min": 45.0,
    "cp-ride2-5min": 65.0,
    "cp-ride3-10min": 85.0,
    "cp-ride4-20min": 95.0,
    "cp-ride5-mixed": 120.0,
    "test-ride": 50.0,
    "breakthrough-5min": 75.0,
}


class MockXertClient:
    """
    Mock Xert client for E2E testing.

    Returns activities based on FIT files in the fixtures directory.
    Each FIT file becomes an activity with a predictable ID derived from filename.
    """

    def __init__(self):
        self._fixtures_dir = Path(os.environ.get("MOCK_XERT_FIXTURES_DIR", DEFAULT_FIXTURES_DIR))
        self._logged_in = False
        self._username: str | None = None
        # Use %r to escape special characters and prevent log injection
        logger.info("MockXertClient initialized with fixtures_dir=%r", self._fixtures_dir)

    async def login(self, username: str, password: str) -> None:
        """Simulate Xert login. Always succeeds unless password is 'invalid'."""
        if password == "invalid":
            raise XertAPIError("Invalid Xert credentials")
        self._logged_in = True
        self._username = username
        # Use %r to escape special characters and prevent log injection
        logger.info("MockXertClient: login successful for %r", username)

    async def list_activities(
        self,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
    ) -> list[XertActivity]:
        """
        Return activities based on FIT files in the fixtures directory.

        Each .fit file becomes an activity. Activity IDs are derived from
        the filename (e.g., 'cp-ride1-2min.fit' -> 'cp-ride1-2min').
        """
        if not self._fixtures_dir.exists():
            # Use %r to escape special characters and prevent log injection
            logger.warning(
                "MockXertClient: fixtures directory does not exist: %r",
                self._fixtures_dir,
            )
            return []

        activities = []
        fit_files = sorted(self._fixtures_dir.glob("*.fit"))

        # Generate activities with staggered timestamps
        base_time = datetime.now() - timedelta(days=len(fit_files))

        for i, fit_path in enumerate(fit_files):
            activity_id = fit_path.stem  # filename without extension
            started_at = base_time + timedelta(days=i, hours=8)

            activities.append(
                XertActivity(
                    id=activity_id,
                    name=f"Mock: {activity_id.replace('-', ' ').title()}",
                    started_at=started_at,
                    activity_type="Cycling",
                    description=f"Mock activity from {fit_path.name}",
                )
            )

        logger.info("MockXertClient: list_activities returning %d activities", len(activities))
        return activities

    async def download_fit(self, activity_id: str) -> bytes:
        """
        Return FIT file bytes for the given activity ID.

        The activity_id should match a filename (without extension) in the
        fixtures directory.
        """
        fit_path = self._fixtures_dir / f"{activity_id}.fit"

        if not fit_path.exists():
            raise XertAPIError(f"FIT file not found for activity: {activity_id}")

        # Use %r to escape special characters and prevent log injection
        logger.info("MockXertClient: download_fit returning %r", fit_path)
        return fit_path.read_bytes()

    async def get_xss(self, activity_id: str) -> float | None:
        """Return mock XSS value for the activity."""
        xss = MOCK_XSS_VALUES.get(activity_id)
        # Use %r to escape special characters and prevent log injection
        logger.info("MockXertClient: get_xss(%r) = %s", activity_id, xss)
        return xss

    async def close(self) -> None:
        """No-op for mock client."""
        pass


def is_mock_enabled() -> bool:
    """Check if Xert mock is enabled via environment variable."""
    return os.environ.get("MOCK_XERT_ENABLED", "").lower() in ("true", "1", "yes")


def setup_mock_xert_client() -> None:
    """
    Configure the Xert client factory to use MockXertClient if enabled.

    Call this at application startup (e.g., in app.py or a startup event).
    """
    if is_mock_enabled():
        from trainingdash.integrations.xert import set_xert_client_factory

        set_xert_client_factory(MockXertClient)
        logger.info("Xert mock client enabled for E2E testing")
