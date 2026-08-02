import asyncio
import os
import sys

from sqlalchemy import text

from trainingdash.db import async_session, engine
from trainingdash.models import Base, User
from trainingdash.auth import hash_password


async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)

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