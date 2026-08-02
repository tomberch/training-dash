import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    encryption_key: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql+asyncpg://trainingdash:trainingdash@localhost:5432/trainingdash",
            ),
            secret_key=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
            encryption_key=os.environ.get("TRAININGDASH_ENCRYPTION_KEY"),
        )


settings = Settings.from_env()