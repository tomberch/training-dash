"""
Common sync orchestration pattern for external integrations (Xert, Garmin, etc).

This module extracts the shared sync logic that was duplicated between
sync_xert_job and sync_garmin_job. Each provider implements a SyncProvider
that handles the provider-specific authentication and activity fetching.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    def extract_credentials(self, creds: Any) -> CredentialInfo:
        """
        Extract all credential fields needed by run_sync() from the model.

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

    cred_info = provider.extract_credentials(creds)

    # Decrypt password
    try:
        password = decrypt(cred_info.encrypted_password)
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
        cred_info, existing_refs
    )

    log_prefix = f"sync_{provider.source_name}"
    if is_first_sync:
        if cred_info.sync_since:
            logger.info(
                "%s: First sync for user %s, using sync_since %s",
                log_prefix, user_id, cred_info.sync_since,
            )
        else:
            logger.info(
                "%s: First sync for user %s, no sync_since set, using 90 days",
                log_prefix, user_id,
            )
    else:
        if cred_info.last_synced_at:
            logger.info(
                "%s: Incremental sync for user %s, using last_synced_at %s - 4h",
                log_prefix, user_id, cred_info.last_synced_at,
            )
        else:
            logger.info(
                "%s: Subsequent sync for user %s, no last_synced_at, using 90 days",
                log_prefix, user_id,
            )

    # Connect to provider
    try:
        await provider.connect(cred_info.email, password)
    except Exception as e:
        logger.error(f"{log_prefix}: Failed to connect for user {user_id}: {e}")
        return SyncResult(
            success=False,
            user_id=user_id,
            error=str(e),
        )
    
    try:
        # List activities
        try:
            activities = await provider.list_activities(start_date, end_date)
        except Exception as e:
            logger.error(
                "%s: Failed to list activities for user %s: %s",
                log_prefix, user_id, e,
            )
            return SyncResult(success=False, user_id=user_id, error=str(e))
        
        # Filter to new activities (not already imported from this source)
        new_activities = [
            a for a in activities 
            if provider.make_source_ref(a.id) not in existing_refs
        ]
        
        if not new_activities:
            logger.info(f"{log_prefix}: No new activities for user {user_id}")
            # Still update last_synced_at so the next sync uses a tight window
            await _write_last_synced_at(db, creds)
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

        # Record the successful sync time so the next sync uses an incremental window
        await _write_last_synced_at(db, creds)

        return SyncResult(
            success=True,
            user_id=user_id,
            synced_activities=synced,
            skipped_duplicates=skipped_duplicates,
        )
        
    finally:
        await provider.close()


async def _write_last_synced_at(
    db: AsyncSession,
    creds: Any,
) -> None:
    """
    Stamp last_synced_at = now(UTC) on the credentials row.

    Called after every successful sync (including no-new-activities runs) so
    that _determine_sync_range can use an incremental 4-hour window next time.
    Uses ORM mutation rather than raw DDL so the session identity map stays
    consistent.
    """
    creds.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()


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
    cred_info: CredentialInfo,
    existing_refs: set[str],
) -> tuple[datetime, datetime, bool]:
    """
    Determine sync date range.

    Priority order:
      1. First sync (no existing activities): use sync_since if set, else 90 days.
      2. Subsequent sync with last_synced_at: use last_synced_at - 4h (incremental).
      3. Subsequent sync without last_synced_at: fall back to 90 days.

    Returns (start_date, end_date, is_first_sync).
    """
    end_date = datetime.now(timezone.utc).replace(tzinfo=None)
    is_first_sync = len(existing_refs) == 0

    if is_first_sync:
        sync_since = cred_info.sync_since
        if sync_since is not None:
            # sync_since may be a date or a datetime
            if hasattr(sync_since, "hour"):
                start_date = sync_since
            else:
                start_date = datetime.combine(sync_since, datetime.min.time())
        else:
            start_date = end_date - timedelta(days=90)
    else:
        last_synced_at = cred_info.last_synced_at
        if last_synced_at is not None:
            # Incremental window: last sync time minus 4-hour buffer to catch
            # activities that were still uploading when the last sync ran.
            start_date = last_synced_at - timedelta(hours=4)
        else:
            # No last_synced_at recorded yet — fall back to 90 days
            start_date = end_date - timedelta(days=90)

    return start_date, end_date, is_first_sync
