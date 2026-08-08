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
from trainingdash.repositories.postgres.user_repo import PostgresUserRepo


async def get_activity_repo(db: DbSession) -> PostgresActivityRepo:
    """Create an ActivityRepo bound to the current session."""
    return PostgresActivityRepo(db)


async def get_user_repo(db: DbSession) -> PostgresUserRepo:
    """Create a UserRepo bound to the current session."""
    return PostgresUserRepo(db)


# Annotated types for use in router function signatures
ActivityRepoD = Annotated[PostgresActivityRepo, Depends(get_activity_repo)]
UserRepoD = Annotated[PostgresUserRepo, Depends(get_user_repo)]
