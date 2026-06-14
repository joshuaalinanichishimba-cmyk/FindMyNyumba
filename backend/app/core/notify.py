"""
app/core/notify.py

Tiny helper to create in-app Notification rows. Used wherever the platform
needs to alert a user (viewing approved/rejected/rescheduled, new message,
listing approved, etc.).

Design notes:
  - Matches the EXISTING Notification model in app/models/admin_models.py,
    whose columns are: user_id, type, title, body, channel, read_at, created_at.
    (No `message`/`is_read` columns -- read state is `read_at IS NULL`.)
  - Exception-safe: a notification failure must never roll back or 500 the
    main request (e.g. approving a viewing). On error we roll back only this
    helper's pending change and swallow the exception.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.admin_models import Notification

# Stable type tags the frontend can switch icons/colours on.
VIEWING_REQUESTED   = "viewing_requested"
VIEWING_APPROVED    = "viewing_approved"
VIEWING_REJECTED    = "viewing_rejected"
VIEWING_RESCHEDULED = "viewing_rescheduled"
VIEWING_CANCELLED   = "viewing_cancelled"
MESSAGE_NEW         = "message"
LISTING_APPROVED    = "listing_approved"
LISTING_REJECTED    = "listing_rejected"


def push_notification(
    db: Session,
    user_id: Optional[int],
    ntype: str,
    title: str,
    body: Optional[str] = None,
    commit: bool = True,
) -> Optional[Notification]:
    """Create a notification for `user_id` (None = admin broadcast).

    Returns the row on success, or None on failure (never raises)."""
    try:
        n = Notification(
            user_id=user_id,
            type=ntype,
            title=title,
            body=body,
            channel="in_app",
        )
        db.add(n)
        if commit:
            db.commit()
            db.refresh(n)
        return n
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None
