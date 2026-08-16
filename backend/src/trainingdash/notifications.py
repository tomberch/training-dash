"""
Notification helpers — centralized notification creation with pruning.

Keeps at most MAX_NOTIFICATIONS_PER_USER notifications per user by deleting
the oldest dismissed ones when the limit is exceeded.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Notification

MAX_NOTIFICATIONS_PER_USER = 50


async def create_notification(
    db: AsyncSession,
    user_id: int,
    notification_type: str,
    message: str,
    payload: str | None = None,
    status: str = "pending",
) -> Notification:
    """
    Create a notification and prune old ones if over the limit.

    Pruning deletes the oldest dismissed notifications first, then oldest
    accepted ones if needed. Pending notifications are never auto-deleted.

    Args:
        db: Database session
        user_id: User to notify
        notification_type: Type identifier (e.g., "ftp_suggestion", "sync_duplicates_skipped")
        message: Human-readable message
        payload: Optional JSON payload string
        status: Initial status (default "pending")

    Returns:
        The created Notification instance
    """
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        message=message,
        payload=payload,
        status=status,
    )
    db.add(notification)
    await db.flush()

    # Check total count for this user
    count_result = await db.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
    )
    total_count = count_result.scalar() or 0

    if total_count > MAX_NOTIFICATIONS_PER_USER:
        excess = total_count - MAX_NOTIFICATIONS_PER_USER

        # Delete oldest dismissed notifications first
        dismissed_to_delete = await db.execute(
            select(Notification.id)
            .where(
                Notification.user_id == user_id,
                Notification.status == "dismissed",
            )
            .order_by(Notification.created_at.asc())
            .limit(excess)
        )
        dismissed_ids = list(dismissed_to_delete.scalars().all())

        if dismissed_ids:
            await db.execute(delete(Notification).where(Notification.id.in_(dismissed_ids)))
            excess -= len(dismissed_ids)

        # If still over limit, delete oldest accepted notifications
        if excess > 0:
            accepted_to_delete = await db.execute(
                select(Notification.id)
                .where(
                    Notification.user_id == user_id,
                    Notification.status == "accepted",
                )
                .order_by(Notification.created_at.asc())
                .limit(excess)
            )
            accepted_ids = list(accepted_to_delete.scalars().all())

            if accepted_ids:
                await db.execute(delete(Notification).where(Notification.id.in_(accepted_ids)))

    return notification
