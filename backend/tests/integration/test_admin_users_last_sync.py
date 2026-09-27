"""Integration tests for per-user last_synced_at in the admin users list (ADR 0007)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from trainingdash.crypto import encrypt
from trainingdash.repositories.postgres.models import User


async def test_admin_users_includes_last_synced_at(auth_client, db_session, seed_user):
    """The user list carries the most recent sync timestamp across credentials."""
    await db_session.execute(
        text(
            """INSERT INTO xert_credentials (user_id, xert_email, encrypted_password, sync_enabled, last_synced_at)
            VALUES (:uid, 'u@xert.com', 'x', true, CAST(:ts AS timestamp))"""
        ).bindparams(
            uid=seed_user.id,
            ts=(datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)).isoformat(),
        )
    )
    await db_session.commit()

    response = await auth_client.get("/api/admin/users")
    assert response.status_code == 200
    users = response.json()
    me = next(u for u in users if u["id"] == seed_user.id)
    assert me["last_synced_at"] is not None
    # other users (no credentials) report null
    other = next(u for u in users if u["email"] == "user2@example.com") if any(
        u["email"] == "user2@example.com" for u in users
    ) else None
    if other:
        assert other["last_synced_at"] is None


async def test_admin_users_last_synced_at_null_without_credentials(auth_client, db_session):
    user = User(email="nosync@example.com", password_hash="x" * 12)
    db_session.add(user)
    await db_session.commit()

    response = await auth_client.get("/api/admin/users")
    assert response.status_code == 200
    me = next(u for u in response.json() if u["email"] == "nosync@example.com")
    assert me["last_synced_at"] is None