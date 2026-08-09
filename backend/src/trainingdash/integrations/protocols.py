"""
Protocols for external integrations.

Defines abstract interfaces that sync providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Activity

# Type variable for provider-specific activity type
TActivity = TypeVar("TActivity")


@dataclass
class CredentialInfo:
    """Normalised credential values extracted from a provider's credentials model."""

    email: str
    encrypted_password: bytes
    sync_since: datetime | None
    last_synced_at: datetime | None


@dataclass
class ProviderActivity(Generic[TActivity]):
    """Wrapper for provider-specific activity with common fields."""

    id: str
    started_at: datetime
    distance_m: float
    raw: TActivity  # The original provider-specific activity object


class SyncProvider(ABC, Generic[TActivity]):
    """
    Abstract base class for sync providers (Xert, Garmin, etc).

    Subclasses implement provider-specific authentication and activity fetching,
    while the common sync orchestration logic lives in the SyncFromProvider use case.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Provider identifier used in Activity.source (e.g., 'xert', 'garmin')."""
        ...

    @property
    @abstractmethod
    def credentials_model(self) -> type:
        """SQLAlchemy model class for this provider's credentials."""
        ...

    @abstractmethod
    def extract_credentials(self, creds: Any) -> CredentialInfo:
        """
        Extract all credential fields needed by the SyncFromProvider use case from the model.

        Hides the field-name differences between providers (e.g.
        XertCredentials.xert_email vs GarminCredentials.garmin_email).
        Returns a CredentialInfo with email, encrypted_password, sync_since,
        and last_synced_at.
        """
        ...

    @abstractmethod
    async def connect(self, email: str, password: str) -> None:
        """
        Connect and authenticate with the provider.

        Raises provider-specific exceptions on failure.
        """
        ...

    @abstractmethod
    async def list_activities(self, start_date: datetime, end_date: datetime) -> list[ProviderActivity[TActivity]]:
        """
        List activities in the date range.

        Returns ProviderActivity wrappers with common fields extracted.
        """
        ...

    @abstractmethod
    async def ingest_activity(
        self,
        db: AsyncSession,
        user_id: int,
        activity: ProviderActivity[TActivity],
        batch_mode: bool,
    ) -> Activity | None:
        """
        Ingest a single activity into the database.

        This should call the appropriate ingest function (ingest_fit for FIT files,
        ingest_xert_activity for Xert session data, etc).

        Returns the created Activity or None if ingestion failed.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the provider connection."""
        ...

    def make_source_ref(self, activity_id: str) -> str:
        """Generate source_ref for an activity."""
        return f"{self.source_name}:{activity_id}"
