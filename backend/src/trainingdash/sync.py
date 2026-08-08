"""
Common sync orchestration pattern for external integrations (Xert, Garmin, etc).

This module provides backward compatibility exports. The actual sync logic
has been moved to trainingdash.use_cases.sync_from_provider.SyncFromProvider.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.integrations.protocols import (
    CredentialInfo,
    ProviderActivity,
    SyncProvider,
)
from trainingdash.use_cases.sync_from_provider import SyncFromProvider, SyncResult

# Re-export for backward compatibility
__all__ = [
    "CredentialInfo",
    "ProviderActivity",
    "SyncProvider",
    "SyncResult",
    "run_sync",
    "_determine_sync_range",
]


async def run_sync(
    db: AsyncSession,
    user_id: int,
    provider: SyncProvider,
) -> SyncResult:
    """
    Run sync for a user using the given provider.
    
    This is a thin wrapper around SyncFromProvider.execute() for backward
    compatibility. New code should use the use case directly.
    """
    use_case = SyncFromProvider(db)
    return await use_case.execute(user_id, provider)


# Expose _determine_sync_range for unit tests
def _determine_sync_range(cred_info: CredentialInfo, existing_refs: set[str]):
    """
    Determine sync date range.
    
    Backward compatibility wrapper - delegates to use case's static method.
    """
    # Create a temporary instance to access the method
    # The method doesn't use self._db, so we can pass None
    use_case = SyncFromProvider(None)  # type: ignore[arg-type]
    return use_case._determine_sync_range(cred_info, existing_refs)
