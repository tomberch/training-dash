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
    
    Xert provides session_data (per-second data) via their OAuth API,
    not FIT files. Activities are ingested via ingest_xert_activity().
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
        await self._client.login(email, password)
    
    async def list_activities(
        self, start_date: datetime, end_date: datetime
    ) -> list[ProviderActivity]:
        """List Xert activities in date range."""
        # Convert to timestamps
        from_ts = int(start_date.timestamp())
        to_ts = int(end_date.timestamp())
        
        activities = await self._client.list_activities(
            from_timestamp=from_ts, to_timestamp=to_ts
        )
        
        # Wrap in ProviderActivity with common fields
        # Note: XertActivity from list doesn't have distance, only XertActivityDetail does
        # We use 0 here; actual distance comes from detail when ingesting
        result = []
        for a in activities:
            result.append(ProviderActivity(
                id=str(a.id),
                started_at=a.started_at,
                distance_m=0,  # Will be populated from detail during ingest
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
        """Ingest a Xert activity via session_data."""
        from trainingdash.ingest import ingest_xert_activity
        from trainingdash.xert import XertAPIError
        
        source_ref = self.make_source_ref(activity.id)
        
        try:
            # Fetch full activity detail with session_data
            detail = await self._client.get_activity_detail(
                activity.raw, include_session_data=True
            )
            
            # Ingest using the full metric pipeline
            return await ingest_xert_activity(
                db, user_id, detail, source_ref, batch_mode
            )
            
        except XertAPIError as e:
            logger.warning(f"Failed to fetch Xert activity {activity.id}: {e}")
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
