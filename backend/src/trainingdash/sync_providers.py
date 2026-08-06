"""
Sync provider implementations for Xert and Garmin.

These implement the SyncProvider interface from sync.py, handling
provider-specific authentication and activity fetching while the
common orchestration logic lives in run_sync().
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.models import Activity, XertCredentials, GarminCredentials
from trainingdash.sync import SyncProvider, ProviderActivity

logger = logging.getLogger(__name__)


class XertSyncProvider(SyncProvider):
    """
    Xert sync provider.

    Activities are downloaded as raw FIT files via a web session cookie and
    ingested through the standard ingest_fit() pipeline — the same path used
    by Garmin. This gives full field coverage (power, HR, cadence, GPS,
    temperature, grade, left/right balance).

    XSS (Xert Strain Score) is fetched separately via a lightweight OAuth JSON
    call and stored as Activity.training_load. TSS overwrites it once the user
    has a threshold configured.
    """

    def __init__(self):
        self._client = None

    @property
    def source_name(self) -> str:
        return "xert"

    @property
    def credentials_model(self) -> type:
        return XertCredentials

    def get_email(self, creds: XertCredentials) -> str:
        return creds.xert_email

    def get_encrypted_password(self, creds: XertCredentials) -> str:
        return creds.encrypted_password

    def get_sync_since(self, creds: XertCredentials) -> datetime | None:
        return creds.sync_since

    async def connect(self, email: str, password: str) -> None:
        from trainingdash.xert import get_xert_client

        self._client = get_xert_client()
        # login() establishes both the OAuth2 token and the web session cookie
        await self._client.login(email, password)

    async def list_activities(
        self, start_date: datetime, end_date: datetime
    ) -> list[ProviderActivity]:
        """List Xert activities in date range via OAuth API."""
        from_ts = int(start_date.timestamp())
        to_ts = int(end_date.timestamp())

        activities = await self._client.list_activities(
            from_timestamp=from_ts, to_timestamp=to_ts
        )

        result = []
        for a in activities:
            result.append(ProviderActivity(
                id=str(a.id),
                started_at=a.started_at,
                distance_m=0,  # not available from list; ingest_fit() computes it
                raw=a,
            ))

        return result

    async def ingest_activity(
        self,
        db: AsyncSession,
        user_id: int,
        activity: ProviderActivity,
        batch_mode: bool,
    ) -> Activity | None:
        """
        Ingest a Xert activity by downloading its FIT file.

        1. Download FIT bytes via web session (re-login on session expiry)
        2. Ingest through ingest_fit() — same pipeline as Garmin
        3. Fetch XSS from JSON summary and store as training_load
        """
        from trainingdash.ingest import ingest_fit
        from trainingdash.xert import XertAPIError

        source_ref = self.make_source_ref(activity.id)

        try:
            # Download raw FIT file via web session
            fit_bytes = await self._client.download_fit(activity.id)

            # Ingest through the standard FIT pipeline
            ingested = await ingest_fit(
                db, user_id, fit_bytes, "xert", source_ref, batch_mode
            )

            if ingested is not None:
                # Fetch XSS and overwrite training_load set by ingest_fit().
                # ingest_fit() already committed; this second commit persists
                # only the training_load mutation. TSS will overwrite XSS again
                # once the user has a threshold configured.
                xss = await self._client.get_xss(activity.id)
                if xss is not None:
                    ingested.training_load = xss
                    await db.commit()

            return ingested

        except XertAPIError as e:
            logger.warning("Failed to ingest Xert activity %s: %s", activity.id, e)
            return None

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


class GarminSyncProvider(SyncProvider):
    """
    Garmin Connect sync provider.
    
    Garmin provides original FIT files, so activities are ingested
    via the standard ingest_fit() pipeline.
    """
    
    def __init__(self):
        self._client = None
    
    @property
    def source_name(self) -> str:
        return "garmin"
    
    @property
    def credentials_model(self) -> type:
        return GarminCredentials
    
    def get_email(self, creds: GarminCredentials) -> str:
        return creds.garmin_email
    
    def get_encrypted_password(self, creds: GarminCredentials) -> str:
        return creds.encrypted_password
    
    def get_sync_since(self, creds: GarminCredentials) -> datetime | None:
        return creds.sync_since
    
    async def connect(self, email: str, password: str) -> None:
        from trainingdash.garmin import get_garmin_client, GarminMFARequired
        
        self._client = get_garmin_client()
        try:
            self._client.login(email, password)
        except GarminMFARequired:
            raise RuntimeError("MFA required - please re-authenticate in settings")
    
    async def list_activities(
        self, start_date: datetime, end_date: datetime
    ) -> list[ProviderActivity]:
        """List Garmin activities in date range."""
        activities = self._client.list_activities(
            start_date=start_date, end_date=end_date
        )
        
        # Wrap in ProviderActivity with common fields
        result = []
        for a in activities:
            # Garmin activity has: id, started_at, distance_m
            result.append(ProviderActivity(
                id=str(a.id),
                started_at=a.started_at,
                distance_m=a.distance_m or 0,
                raw=a,
            ))
        
        return result
    
    async def ingest_activity(
        self,
        db: AsyncSession,
        user_id: int,
        activity: ProviderActivity,
        batch_mode: bool,
    ) -> Activity | None:
        """Ingest a Garmin activity via FIT file download."""
        from trainingdash.ingest import ingest_fit
        from trainingdash.garmin import GarminAPIError
        
        source_ref = self.make_source_ref(activity.id)
        
        try:
            # Download original FIT file
            fit_bytes = self._client.download_fit(int(activity.id))
            
            # Ingest using standard FIT pipeline
            return await ingest_fit(
                db, user_id, fit_bytes, "garmin", source_ref, batch_mode
            )
            
        except GarminAPIError as e:
            logger.warning(f"Failed to download Garmin activity {activity.id}: {e}")
            return None
    
    async def close(self) -> None:
        # Garmin client doesn't need explicit close
        self._client = None
