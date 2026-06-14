"""
app/api/v1/endpoints/notifications.py

Notification center API for end users (students, hosts, landlords).

  GET   /notifications                list my notifications (newest first)
  GET   /notifications/unread-count   badge count
  PATCH /notifications/{id}/read      mark one as read
  PATCH /notifications/read-all       mark all of mine as read

Backed by the existing Notification model (app/models/admin_models.py):
  user_id, type, title, body, channel, read_at, created_at
Read state is derived: read = (read_at IS NOT NULL).

Scope: every query is filtered to current_user.id, so a user can only ever see
or mutate their own notifications.

Registration (app/api/v1/api.py):
    from app.api.v1.endpoints.notifications import router as notifications_router
    api_router.include_router(notifications_router)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.admin_models import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _serialize(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "is_read": n.read_at is not None,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
def list_notifications(
    only_unread: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if only_unread:
        q = q.filter(Notification.read_at.is_(None))
    rows = q.order_by(Notification.created_at.desc()).limit(limit).all()
    return [_serialize(n) for n in rows]


@router.get("/unread-count")
def unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .count()
    )
    return {"unread_count": count}


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(n)
    return {"status": "success", "notification": _serialize(n)}


@router.patch("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .update({"read_at": datetime.now(timezone.utc)}, synchronize_session=False)
    )
    db.commit()
    return {"status": "success", "marked": updated}
