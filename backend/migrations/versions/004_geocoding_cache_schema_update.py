"""Update geocoding_cache table to use cache_key and result_json columns.

The original schema stored structured columns (lat, lon, city, region, country).
The new schema uses cache_key as primary key and stores JSON results, which:
- Supports cache keys with precision and locality flags
- Stores complete GeocodedPlace objects including place_type
- Enables negative caching (storing None results)

Revision ID: 004_geocoding_cache_update
Revises: 003_cache_stats
Create Date: 2026-08-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_geocoding_cache_update"
down_revision: str | None = "003_cache_stats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old table and create the new schema
    # The old data cannot be migrated as the cache_key format is different
    op.drop_index("ix_geocoding_cache_coords", table_name="geocoding_cache")
    op.drop_table("geocoding_cache")

    op.create_table(
        "geocoding_cache",
        sa.Column("cache_key", sa.String(100), primary_key=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    # Recreate the old schema
    op.drop_table("geocoding_cache")

    op.create_table(
        "geocoding_cache",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("region", sa.String(255), nullable=True),
        sa.Column("country", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_geocoding_cache_coords", "geocoding_cache", ["lat", "lon"])
