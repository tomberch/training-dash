"""
Common sync orchestration pattern for external integrations (Xert, Garmin, etc).

This module extracts the shared sync logic that was duplicated between
sync_xert_job and sync_garmin_job. Each provider implements a SyncProvider
that handles the provider-specific authentication and activity fetching.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.crypto import decrypt, EncryptionError
from trainingdash.ingest import is_duplicate_activity, finalize_batch_import
from trainingdash.models import Activity

logger = logging.getLogger(__name__)

# Type variable for provider-specific activity type
TActivity = TypeVar("TActivity")


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    user_id: int
    synced_activities: int = 0
    skipped_duplicates: int = 0
    error: str | None = None


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
    while the common sync orchestration logic lives in run_sync().
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
    def get_email(self, creds: Any) -> str:
        """Extract email/username from credentials model."""
        ...
    
    @abstractmethod
    def get_encrypted_password(self, creds: Any) -> str:
        """Extract encrypted password from credentials model."""
        ...
    
    @abstractmethod
    def get_sync_since(self, creds: Any) -> datetime | None:
        """Extract sync_since date from credentials model, if set."""
        ...
    
    @abstractmethod
    async def connect(self, email: str, password: str) -> None:
        """
        Connect and authenticate with the provider.
        
        Raises provider-specific exceptions on failure.
        """
        ...
    
    @abstractmethod
    async def list_activities(
        self, start_date: datetime, end_date: datetime
    ) -> list[ProviderActivity[TActivity]]:
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


async def run_sync(
    db: AsyncSession,
    user_id: int,
    provider: SyncProvider,
) -> SyncResult:
    """
    Run sync for a user using the given provider.
    
    This is the common orchestration logic shared by all sync jobs:
    1. Get and decrypt credentials
    2. Determine sync date range (sync_since for first sync, 90 days otherwise)
    3. Connect to provider
    4. List activities and filter to new ones
    5. Check for duplicates from other sources
    6. Ingest new activities (with batch mode for >10)
    7. Finalize batch import if needed
    
    Args:
        db: Database session
        user_id: User to sync for
        provider: SyncProvider implementation
    
    Returns:
        SyncResult with success status and counts
    """
    # Get credentials
    creds = await _get_credentials(db, user_id, provider)
    if creds is None:
        return SyncResult(
            success=False,
            user_id=user_id,
            error=f"No {provider.source_name.title()} credentials configured",
        )
    
    # Decrypt password
    try:
        password = decrypt(provider.get_encrypted_password(creds))
    except EncryptionError:
        logger.error(f"sync_{provider.source_name}: Failed to decrypt credentials for user {user_id}")
        return SyncResult(
            success=False,
            user_id=user_id,
            error="Failed to decrypt credentials",
        )
    
    # Get existing source_refs to skip already-imported activities
    existing_refs = await _get_existing_refs(db, user_id, provider.source_name)
    
    # Determine sync date range
    start_date, end_date, is_first_sync = _determine_sync_range(
        creds, provider, existing_refs
    )
    
    log_prefix = f"sync_{provider.source_name}"
    if is_first_sync:
        sync_since = provider.get_sync_since(creds)
        if sync_since:
            logger.info(f"{log_prefix}: First sync for user {user_id}, using sync_since {sync_since}")
        else:
            logger.info(f"{log_prefix}: First sync for user {user_id}, no sync_since set, using 90 days")
    else:
        logger.info(f"{log_prefix}: Subsequent sync for user {user_id}, using 90 days")
    
    # Connect to provider
    try:
        await provider.connect(provider.get_email(creds), password)
    except Exception as e:
        logger.error(f"{log_prefix}: Failed to connect for user {user_id}: {e}")
        return SyncResult(
            success=False,
            user_id=user_id,
            error=str(e),
        )
    
    try:
        # List activities
        activities = await provider.list_activities(start_date, end_date)
        
        # Filter to new activities (not already imported from this source)
        new_activities = [
            a for a in activities 
            if provider.make_source_ref(a.id) not in existing_refs
        ]
        
        if not new_activities:
            logger.info(f"{log_prefix}: No new activities for user {user_id}")
            return SyncResult(success=True, user_id=user_id)
        
        # Use batch mode if >10 activities to avoid notification spam
        batch_mode = len(new_activities) > 10
        if batch_mode:
            logger.info(f"{log_prefix}: Using batch mode for {len(new_activities)} activities")
        
        # Ingest each activity
        synced = 0
        skipped_duplicates = 0
        
        for activity in new_activities:
            try:
                # Check for duplicates from other sources
                is_dup = await is_duplicate_activity(
                    db,
                    user_id,
                    activity.started_at,
                    activity.distance_m,
                    provider.source_name,
                )
                if is_dup:
                    skipped_duplicates += 1
                    logger.info(
                        f"{log_prefix}: Skipped duplicate {provider.make_source_ref(activity.id)} "
                        f"for user {user_id}"
                    )
                    continue
                
                # Ingest the activity
                result = await provider.ingest_activity(db, user_id, activity, batch_mode)
                
                if result is not None:
                    synced += 1
                    logger.info(
                        f"{log_prefix}: Created activity {result.id} from "
                        f"{provider.make_source_ref(activity.id)} for user {user_id}"
                    )
                else:
                    logger.warning(
                        f"{log_prefix}: Failed to ingest activity {activity.id} for user {user_id}"
                    )
                    
            except Exception as e:
                logger.exception(
                    f"{log_prefix}: Unexpected error processing activity {activity.id}"
                )
                continue
        
        logger.info(
            f"{log_prefix}: Synced {synced} activities, skipped {skipped_duplicates} duplicates "
            f"for user {user_id}"
        )
        
        # Finalize batch import if needed
        if batch_mode and synced > 0:
            await finalize_batch_import(db, user_id, synced)
        
        return SyncResult(
            success=True,
            user_id=user_id,
            synced_activities=synced,
            skipped_duplicates=skipped_duplicates,
        )
        
    finally:
        await provider.close()


async def _get_credentials(
    db: AsyncSession,
    user_id: int,
    provider: SyncProvider,
) -> Any | None:
    """Get credentials for a user and provider."""
    model = provider.credentials_model
    result = await db.execute(
        select(model).where(model.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _get_existing_refs(
    db: AsyncSession,
    user_id: int,
    source: str,
) -> set[str]:
    """Get existing source_refs for a user and source."""
    result = await db.execute(
        select(Activity.source_ref).where(
            Activity.user_id == user_id,
            Activity.source == source,
        )
    )
    return set(result.scalars().all())


def _determine_sync_range(
    creds: Any,
    provider: SyncProvider,
    existing_refs: set[str],
) -> tuple[datetime, datetime, bool]:
    """
    Determine sync date range based on whether this is first sync.
    
    Returns (start_date, end_date, is_first_sync)
    """
    from datetime import timezone
    
    end_date = datetime.now(timezone.utc).replace(tzinfo=None)
    is_first_sync = len(existing_refs) == 0
    
    if is_first_sync:
        sync_since = provider.get_sync_since(creds)
        if sync_since is not None:
            # sync_since might be a date or datetime
            if hasattr(sync_since, 'hour'):
                start_date = sync_since
            else:
                start_date = datetime.combine(sync_since, datetime.min.time())
        else:
            # Default to 90 days
            start_date = end_date - timedelta(days=90)
    else:
        # Subsequent sync: always use 90 days
        start_date = end_date - timedelta(days=90)
    
    return start_date, end_date, is_first_sync
