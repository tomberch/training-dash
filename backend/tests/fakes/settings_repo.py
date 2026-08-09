"""In-memory fake implementation of AppSettingsRepo for testing."""

from trainingdash.repositories.postgres.models import AppSettings


class FakeAppSettingsRepo:
    """
    In-memory fake implementation of AppSettingsRepo protocol.

    Stores settings in a dict keyed by setting key.
    """

    def __init__(self) -> None:
        self._settings: dict[str, str] = {}

    # --- Protocol methods ---

    async def get(self, key: str) -> str | None:
        return self._settings.get(key)

    async def get_bool(self, key: str, default: bool = False) -> bool:
        value = self._settings.get(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes")

    async def set(self, key: str, value: str) -> None:
        self._settings[key] = value

    async def list_all(self) -> list[AppSettings]:
        return [AppSettings(key=k, value=v) for k, v in self._settings.items()]

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored settings."""
        self._settings.clear()

    def get_sync(self, key: str) -> str | None:
        """Synchronous getter for test assertions."""
        return self._settings.get(key)
