"""
FastAPI dependency injection for repositories and use cases.

This module provides factory functions that create repository instances
wired to the current database session. Routers use these as FastAPI
dependencies via Annotated types.

Example usage in a router:
    from trainingdash.dependencies import ActivityRepoD, UserRepoD

    @router.get("/activities/{activity_id}")
    async def get_activity(repo: ActivityRepoD, activity_id: UUID):
        return await repo.get_by_id(activity_id, user_id)
"""

from typing import Annotated

from fastapi import Depends

from trainingdash.auth import DbSession
from trainingdash.repositories.postgres.activity_repo import PostgresActivityRepo
from trainingdash.repositories.postgres.audit_log_repo import PostgresAuditLogRepo
from trainingdash.repositories.postgres.credentials_repo import (
    PostgresGarminCredentialsRepo,
    PostgresXertCredentialsRepo,
)
from trainingdash.repositories.postgres.notification_repo import PostgresNotificationRepo
from trainingdash.repositories.postgres.oauth_link_repo import PostgresOAuthLinkRepo
from trainingdash.repositories.postgres.recalculation_job_repo import (
    PostgresRecalculationJobRepo,
)
from trainingdash.repositories.postgres.settings_repo import PostgresAppSettingsRepo
from trainingdash.repositories.postgres.user_repo import PostgresUserRepo


async def get_activity_repo(db: DbSession) -> PostgresActivityRepo:
    """Create an ActivityRepo bound to the current session."""
    return PostgresActivityRepo(db)


async def get_user_repo(db: DbSession) -> PostgresUserRepo:
    """Create a UserRepo bound to the current session."""
    return PostgresUserRepo(db)


async def get_xert_credentials_repo(db: DbSession) -> PostgresXertCredentialsRepo:
    """Create an XertCredentialsRepo bound to the current session."""
    return PostgresXertCredentialsRepo(db)


async def get_garmin_credentials_repo(db: DbSession) -> PostgresGarminCredentialsRepo:
    """Create a GarminCredentialsRepo bound to the current session."""
    return PostgresGarminCredentialsRepo(db)


async def get_notification_repo(db: DbSession) -> PostgresNotificationRepo:
    """Create a NotificationRepo bound to the current session."""
    return PostgresNotificationRepo(db)


async def get_app_settings_repo(db: DbSession) -> PostgresAppSettingsRepo:
    """Create an AppSettingsRepo bound to the current session."""
    return PostgresAppSettingsRepo(db)


async def get_audit_log_repo(db: DbSession) -> PostgresAuditLogRepo:
    """Create an AuditLogRepo bound to the current session."""
    return PostgresAuditLogRepo(db)


async def get_recalculation_job_repo(db: DbSession) -> PostgresRecalculationJobRepo:
    """Create a RecalculationJobRepo bound to the current session."""
    return PostgresRecalculationJobRepo(db)


async def get_oauth_link_repo(db: DbSession) -> PostgresOAuthLinkRepo:
    """Create an OAuthLinkRepo bound to the current session."""
    return PostgresOAuthLinkRepo(db)


# Annotated types for use in router function signatures
ActivityRepoD = Annotated[PostgresActivityRepo, Depends(get_activity_repo)]
UserRepoD = Annotated[PostgresUserRepo, Depends(get_user_repo)]
XertCredentialsRepoD = Annotated[
    PostgresXertCredentialsRepo, Depends(get_xert_credentials_repo)
]
GarminCredentialsRepoD = Annotated[
    PostgresGarminCredentialsRepo, Depends(get_garmin_credentials_repo)
]
NotificationRepoD = Annotated[PostgresNotificationRepo, Depends(get_notification_repo)]
AppSettingsRepoD = Annotated[PostgresAppSettingsRepo, Depends(get_app_settings_repo)]
AuditLogRepoD = Annotated[PostgresAuditLogRepo, Depends(get_audit_log_repo)]
RecalculationJobRepoD = Annotated[
    PostgresRecalculationJobRepo, Depends(get_recalculation_job_repo)
]
OAuthLinkRepoD = Annotated[PostgresOAuthLinkRepo, Depends(get_oauth_link_repo)]
