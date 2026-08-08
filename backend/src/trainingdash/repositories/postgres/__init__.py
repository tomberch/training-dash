"""
PostgreSQL repository implementations.

This package contains:
- db.py: Database session management and engine setup
- models.py: SQLAlchemy ORM models
- *_repo.py: Repository implementations (added in subsequent tickets)

Import from submodules directly:
    from trainingdash.repositories.postgres.db import async_session, Base
    from trainingdash.repositories.postgres.models import User, Activity
"""

# Don't auto-import here to avoid circular imports and issues with alembic.
# Import directly from db.py and models.py as needed.
