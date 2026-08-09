"""In-memory fake implementation of OAuthLinkRepo for testing."""

from trainingdash.repositories.postgres.models import UserOAuthLink


class FakeOAuthLinkRepo:
    """
    In-memory fake implementation of OAuthLinkRepo protocol.

    Stores links in a dict keyed by (user_id, provider).
    """

    def __init__(self) -> None:
        self._links: dict[tuple[int, str], UserOAuthLink] = {}

    # --- Protocol methods ---

    async def get_by_provider_id(self, provider: str, provider_user_id: str) -> UserOAuthLink | None:
        for link in self._links.values():
            if link.provider == provider and link.provider_user_id == provider_user_id:
                return link
        return None

    async def list_for_user(self, user_id: int) -> list[UserOAuthLink]:
        return [link for (uid, _), link in self._links.items() if uid == user_id]

    async def get_for_user(self, user_id: int, provider: str) -> UserOAuthLink | None:
        return self._links.get((user_id, provider))

    async def save(
        self,
        user_id: int,
        provider: str,
        provider_user_id: str,
        provider_email: str | None = None,
    ) -> UserOAuthLink:
        key = (user_id, provider)
        link = self._links.get(key)
        if link is None:
            link = UserOAuthLink(
                user_id=user_id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=provider_email,
            )
        else:
            link.provider_user_id = provider_user_id
            link.provider_email = provider_email
        self._links[key] = link
        return link

    async def delete(self, user_id: int, provider: str) -> bool:
        key = (user_id, provider)
        if key in self._links:
            del self._links[key]
            return True
        return False

    async def count_for_user(self, user_id: int) -> int:
        return sum(1 for (uid, _) in self._links if uid == user_id)

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored links."""
        self._links.clear()

    def all(self) -> list[UserOAuthLink]:
        """Return all stored links (for test assertions)."""
        return list(self._links.values())
