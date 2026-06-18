"""
app/core/sessions.py

Session lifecycle helpers for token revocation.

create_session(): called on login; inserts a UserSession row and returns its
id, which the caller embeds in the JWT as the `sid` claim.

is_session_active(): called by get_current_user on every request; returns
False if the session is missing or revoked, so a revoked session rejects the
token even though the JWT itself has not expired.

revoke helpers: used by logout, logout-all, password reset, and suspension.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_session import UserSession


def _client_ip(request):
    """Real client IP, honoring X-Forwarded-For (Render and other proxies set
    this header). Falls back to the direct socket IP. None if unavailable."""
    if request is None:
        return None
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def create_session(db: Session, user_id: int, request=None) -> int:
    """Create a session row for a fresh login. Returns the new session id."""
    ua = None
    ip = None
    if request is not None:
        ua = (request.headers.get("user-agent") or "")[:500] or None
        ip = _client_ip(request)
    s = UserSession(user_id=user_id, user_agent=ua, ip=ip, revoked=False)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s.id


def is_session_active(db: Session, session_id: Optional[int]) -> bool:
    """True only if the session exists and is not revoked. Fail closed."""
    if not session_id:
        return False
    s = db.query(UserSession).filter(UserSession.id == session_id).first()
    if s is None or s.revoked:
        return False
    return True


def revoke_session(db: Session, session_id: int) -> None:
    s = db.query(UserSession).filter(UserSession.id == session_id).first()
    if s and not s.revoked:
        s.revoked = True
        db.commit()


def revoke_all_for_user(db: Session, user_id: int, except_session_id: Optional[int] = None) -> int:
    """Revoke all of a user's active sessions (optionally keeping one). Returns count revoked."""
    q = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.revoked == False,  # noqa: E712
    )
    if except_session_id:
        q = q.filter(UserSession.id != except_session_id)
    n = 0
    for s in q.all():
        s.revoked = True
        n += 1
    db.commit()
    return n


def maybe_alert_new_login(db, user_id: int, request, new_session_id: int) -> None:
    """If this login's IP has not been seen in the user's PRIOR sessions,
    create an in-app 'new sign-in' notification. Skips the user's very first
    login. Never raises - a notification failure must not break login."""
    try:
        from app.core.notify import push_notification

        ip = _client_ip(request)

        # All of this user's sessions except the one just created.
        prior = (
            db.query(UserSession)
              .filter(UserSession.user_id == user_id, UserSession.id != new_session_id)
              .all()
        )
        if not prior:
            return  # first login ever - do not alert

        seen_ips = {s.ip for s in prior if s.ip}
        if ip and ip in seen_ips:
            return  # known IP - no alert

        # New IP (or unknown IP) on a returning account -> alert.
        where = f" from {ip}" if ip else ""
        push_notification(
            db,
            user_id,
            "security.new_login",
            "New sign-in to your account",
            f"We noticed a new sign-in{where}. If this was you, you can ignore this. "
            f"If not, change your password and use 'Log out all other devices' in your settings.",
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
