"""In-memory fake implementations of credential repositories for testing."""

from datetime import datetime

from trainingdash.repositories.postgres.models import GarminCredentials, XertCredentials


class FakeXertCredentialsRepo:
    """
    In-memory fake implementation of XertCredentialsRepo protocol.

    Stores credentials in a dict keyed by user_id.
    """

    def __init__(self) -> None:
        self._credentials: dict[int, XertCredentials] = {}

    # --- Protocol methods ---

    async def get_by_user_id(self, user_id: int) -> XertCredentials | None:
        return self._credentials.get(user_id)

    async def exists(self, user_id: int) -> bool:
        return user_id in self._credentials

    async def save(
        self,
        user_id: int,
        xert_email: str,
        encrypted_password: str,
        sync_since: datetime | None = None,
    ) -> XertCredentials:
        creds = self._credentials.get(user_id)
        if creds is None:
            creds = XertCredentials(
                user_id=user_id,
                xert_email=xert_email,
                encrypted_password=encrypted_password,
                sync_since=sync_since,
            )
        else:
            creds.xert_email = xert_email
            creds.encrypted_password = encrypted_password
            if sync_since is not None:
                creds.sync_since = sync_since
        self._credentials[user_id] = creds
        return creds

    async def delete(self, user_id: int) -> bool:
        if user_id in self._credentials:
            del self._credentials[user_id]
            return True
        return False

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored credentials."""
        self._credentials.clear()

    def all(self) -> list[XertCredentials]:
        """Return all stored credentials (for test assertions)."""
        return list(self._credentials.values())


class FakeGarminCredentialsRepo:
    """
    In-memory fake implementation of GarminCredentialsRepo protocol.

    Stores credentials in a dict keyed by user_id.
    """

    def __init__(self) -> None:
        self._credentials: dict[int, GarminCredentials] = {}

    # --- Protocol methods ---

    async def get_by_user_id(self, user_id: int) -> GarminCredentials | None:
        return self._credentials.get(user_id)

    async def exists(self, user_id: int) -> bool:
        return user_id in self._credentials

    async def save(
        self,
        user_id: int,
        garmin_email: str,
        encrypted_password: str,
        sync_since: datetime | None = None,
    ) -> GarminCredentials:
        creds = self._credentials.get(user_id)
        if creds is None:
            creds = GarminCredentials(
                user_id=user_id,
                garmin_email=garmin_email,
                encrypted_password=encrypted_password,
                sync_since=sync_since,
            )
        else:
            creds.garmin_email = garmin_email
            creds.encrypted_password = encrypted_password
            if sync_since is not None:
                creds.sync_since = sync_since
        self._credentials[user_id] = creds
        return creds

    async def delete(self, user_id: int) -> bool:
        if user_id in self._credentials:
            del self._credentials[user_id]
            return True
        return False

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored credentials."""
        self._credentials.clear()

    def all(self) -> list[GarminCredentials]:
        """Return all stored credentials (for test assertions)."""
        return list(self._credentials.values())
