"""
app/core/permissions.py

Shared role guards. The existing codebase defines `require_admin` separately in
admin.py and admin_extra.py; that duplication is fine but the Trust & Safety
routers reuse this single source so the policy lives in one place.

We add a `moderator` concept: a Trust & Safety reviewer who can action
verifications and reports but is NOT a full admin (can't touch payments, can't
change settings). If you don't want a separate role yet, moderators simply
don't exist and `require_staff` collapses to admin-only â€” nothing breaks.

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
    """Admin OR moderator â€” the Trust & Safety review team."""
    if current_user.role not in STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trust & Safety team access required.",
        )
    return current_user


# ---------------------------------------------------------------------------
# RBAC layer for the FindMyNyumba team structure.
# Added alongside the original guards above. Nothing above is modified.
#   "*"         means every permission
#   "finance.*" means any permission starting with "finance."
# The legacy "admin" role keeps full access so existing endpoints keep working.
# ---------------------------------------------------------------------------

ROLE_CEO          = "ceo"
ROLE_ACQUISITION  = "landlord_acquisition"
ROLE_TRUST        = "trust_safety"
ROLE_FINANCE      = "finance"
ROLE_MARKETING    = "marketing"
ROLE_SUPPORT      = "customer_support"
ROLE_OPERATIONS   = "admin_operations"

ROLE_PERMISSIONS = {
    ROLE_CEO:   {"*"},
    "admin":    {"*"},
    "moderator": {"listings.view", "listings.approve", "listings.reject",
                  "verification.*", "reports.*"},
    ROLE_ACQUISITION: {
        "listings.create", "listings.edit_own", "listings.submit",
        "listings.media", "landlords.view", "landlords.create",
        "visits.schedule",
    },
    ROLE_TRUST: {
        "listings.view", "listings.approve", "listings.reject",
        "listings.suspend", "verification.*", "reports.*",
        "users.suspend", "trust.*", "reviews.*",
    },
    ROLE_FINANCE: {
        "finance.*", "payments.*", "reports.financial", "analytics.view",
    },
    ROLE_MARKETING: {
        "analytics.view", "marketing.*", "content.*",
    },
    ROLE_SUPPORT: {
        "students.view", "messages.view", "tickets.*", "support.*", "reports.*",
    },
    ROLE_OPERATIONS: {
        "staff.*", "documents.*", "tasks.*", "meetings.*", "announcements.*",
    },
}

RBAC_ROLES = set(ROLE_PERMISSIONS.keys())


def _granted_for(role):
    """
    Permissions for a role. Reads the RolePermission table first so the admin
    matrix UI is the single source of truth; falls back to ROLE_PERMISSIONS
    when the table is empty (fresh install).
    """
    role = (role or "").lower()
    try:
        from app.core.database import SessionLocal
        from app.models.admin_models import RolePermission
        db = SessionLocal()
        try:
            rows = db.query(RolePermission).filter(RolePermission.role == role).all()
            if rows:
                return {r.permission for r in rows}
        finally:
            db.close()
    except Exception:
        pass
    try:
        from app.api.v1.endpoints.admin_extra import RBAC_DEFAULTS
        if role in RBAC_DEFAULTS:
            return set(RBAC_DEFAULTS[role])
    except Exception:
        pass
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role, permission):
    granted = _granted_for(role)
    if "*" in granted or permission in granted:
        return True
    for g in granted:
        if g.endswith(".*") and permission.startswith(g[:-1]):
            return True
    return False


def is_staff(role):
    """True for any FindMyNyumba team role (wider than the original STAFF_ROLES)."""
    return (role or "").lower() in RBAC_ROLES


def require(permission):
    """Dependency factory: Depends(require("finance.view"))"""
    def _dep(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(getattr(current_user, "role", ""), permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action.",
            )
        return current_user
    return _dep
