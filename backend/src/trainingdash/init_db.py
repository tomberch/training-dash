import asyncio
import os
import subprocess
import sys

from sqlalchemy import text

from trainingdash.db import async_session, engine
from trainingdash.models import User
from trainingdash.auth import hash_password


def run_alembic_upgrade():
    """Run alembic upgrade head using sync subprocess."""
    # Get database URL and convert to sync driver for alembic
    from trainingdash.config import settings
    db_url = settings.database_url
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Alembic upgrade failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout)


async def init_db():
    # Ensure PostGIS extension exists
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    # Run alembic migrations
    run_alembic_upgrade()

    # Seed admin user if not exists
    async with async_session() as session:
        result = await session.execute(
            text("SELECT count(*) FROM users WHERE username = :u"),
            {"u": "admin"},
        )
        count = result.scalar()
        if count == 0:
            user = User(
                username="admin",
                password_hash=hash_password(os.environ.get("ADMIN_PASSWORD", "admin")),
                is_admin=True,
            )
            session.add(user)
            await session.commit()
            print("Created seed admin user (password: admin)")
        else:
            print("Admin user already exists")


if __name__ == "__main__":
    asyncio.run(init_db())
    sys.exit(0)
