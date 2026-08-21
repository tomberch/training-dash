import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    encryption_key: str | None
    open_topo_data_url: str
    open_topo_data_dataset: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql+asyncpg://trainingdash:trainingdash@localhost:5432/trainingdash",
            ),
            secret_key=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
            encryption_key=os.environ.get("TRAININGDASH_ENCRYPTION_KEY"),
            open_topo_data_url=os.environ.get(
                "OPEN_TOPO_DATA_URL",
                "https://api.opentopodata.org/v1",
            ),
            open_topo_data_dataset=os.environ.get(
                "OPEN_TOPO_DATA_DATASET",
                "mapzen",  # Global coverage; use "ned10m" for higher-res US data
            ),
        )


settings = Settings.from_env()
