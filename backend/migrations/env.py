import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url from environment variable if set
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # Convert async URL to sync for Alembic
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", database_url)
else:
    # Also convert the default URL from ini file
    url = config.get_main_option("sqlalchemy.url")
    if url and "+asyncpg" in url:
        config.set_main_option("sqlalchemy.url", url.replace("+asyncpg", ""))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base directly from models module, avoiding db.py which creates async engine
# We need to construct it here to avoid the async driver issue
import importlib.util
import sys

from sqlalchemy.orm import DeclarativeBase

# Load models module without importing db.py
spec = importlib.util.spec_from_file_location(
    "models_for_alembic",
    os.path.join(os.path.dirname(__file__), "..", "src", "trainingdash", "repositories", "postgres", "models.py"),
)


# We need Base from db.py, but it's just a DeclarativeBase - recreate it
class Base(DeclarativeBase):
    pass


# Now manually import the models file content to get the metadata
# Actually, let's just import the models after patching
# Patch sys.modules to provide a fake db module
class FakeDb:
    Base = Base


sys.modules["trainingdash.repositories.postgres.db"] = FakeDb()

# Now we can import models

# Model metadata for autogenerate support
target_metadata = Base.metadata

# Tables that belong to our app (from models.py)
APP_TABLES = {t.name for t in target_metadata.tables.values()}

# PostGIS/tiger tables to ignore
POSTGIS_PREFIXES = (
    "spatial_ref_sys",
    "topology",
    "layer",
    "zip_",
    "county",
    "state",
    "place",
    "addr",
    "faces",
    "edges",
    "featnames",
    "bg",
    "tract",
    "tabblock",
    "cousub",
    "zcta5",
    "loader_",
    "geocode_",
    "pagc_",
    "direction_lookup",
    "secondary_unit_lookup",
    "street_type_lookup",
)


def include_object(obj, name, type_, reflected, compare_to):
    """Filter out PostGIS internal tables from autogenerate."""
    if type_ == "table":
        # Include only our app tables, exclude everything else from DB
        if reflected and name not in APP_TABLES:
            return False
        # Also exclude by prefix for safety
        if any(name.startswith(p) or name == p for p in POSTGIS_PREFIXES):
            return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
