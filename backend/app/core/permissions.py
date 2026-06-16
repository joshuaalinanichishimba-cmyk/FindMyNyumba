"""
app/core/permissions.py

Shared role guards. The existing codebase defines `require_admin` separately in
admin.py and admin_extra.py; that duplication is fine but the Trust & Safety
routers reuse this single source so the policy lives in one place.

We add a `moderator` concept: a Trust & Safety reviewer who can action
verifications and reports but is NOT a full admin (can't touch payments, can't
change settings). If you don't want a separate role yet, moderators simply
don't exist and `require_staff` collapses to admin-only — nothing breaks.

All guards build on app.api.deps.get_current_user, which decodes the JWT
(sub = user id) and already rejects suspended accounts.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User

# Roles allowed to perform Trust & Safety review actions.
STAFF_ROLES = {"admin", "moderator"}


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


def require_staff(current_user: User = Depends(get_current_user)) -> User:
    """Admin OR moderator — the Trust & Safety review team."""
    if current_user.role not in STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trust & Safety team access required.",
        )
    return current_user
