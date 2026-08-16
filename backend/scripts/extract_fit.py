#!/usr/bin/env python3
"""Extract FIT file from database."""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://trainingdash:trainingdash@localhost:5432/trainingdash")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_fit.py <activity_uuid> <output.fit>", file=sys.stderr)
        sys.exit(1)
    
    activity_id = UUID(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        from trainingdash.repositories.postgres.models import Activity
        result = await session.execute(
            select(Activity.raw_fit).where(Activity.id == activity_id)
        )
        raw_fit = result.scalar_one_or_none()
        
        if raw_fit is None:
            print(f"Activity {activity_id} not found or has no FIT data", file=sys.stderr)
            sys.exit(1)
        
        output_path.write_bytes(raw_fit)
        print(f"Extracted {len(raw_fit)} bytes to {output_path}", file=sys.stderr)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
