"""
app/api/v1/endpoints/admin.py

SECURITY UPGRADES:
- Real JWT tokens (via create_access_token) instead of static strings
- bcrypt password verification (via verify_password / get_password_hash)
- Backend role guard on every admin route (require_admin dependency)
- Login rate limiting: 5 attempts -> 15-minute lockout, tracked in DB
- last_login timestamp updated on successful auth
- Change-password endpoint with old-password verification
- Admin-specific forgot/reset password flow
- No plaintext credentials anywhere
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
)
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["Admin"])

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_ATTEMPTS = 5
LOCKOUT_MINS = 15

# ── Password policy ───────────────────────────────────────────────────────────
_PWD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")


def _validate_password(pwd: str) -> None:
    if not _PWD_RE.match(pwd):
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at least 8 characters and include "
                "uppercase, lowercase, a number, and a special character."
            ),
        )


# ── Schemas ───────────────────────────────────────────────────────────────────
class AdminLogin(BaseModel):
    email: str
    password: str


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class AdminForgotPassword(BaseModel):
    email: str


class AdminResetPassword(BaseModel):
    token: str
    new_password: str
    confirm_password: str


class AnnouncementPayload(BaseModel):
    title: str
    body: str
    target: str = "all"


class SettingsPayload(BaseModel):
    platform_name: Optional[str] = None
    support_email: Optional[str] = None
    require_approval: Optional[bool] = None
    maintenance_mode: Optional[bool] = None


# ── Admin guard dependency ────────────────────────────────────────────────────
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforces that the caller is an authenticated admin on every route."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


# ── Rate-limit helpers ────────────────────────────────────────────────────────
def _check_lockout(user: User) -> None:
    if (user.failed_login_attempts or 0) >= MAX_ATTEMPTS and user.lockout_until:
        now = datetime.now(timezone.utc)
        lockout = (
            user.lockout_until.replace(tzinfo=timezone.utc)
            if user.lockout_until.tzinfo is None
            else user.lockout_until
        )
        if now < lockout:
            remaining = int((lockout - now).total_seconds() // 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked. Try again in {remaining} minute(s).",
            )
        # Lockout expired — reset
        user.failed_login_attempts = 0
        user.lockout_until = None


def _record_failure(user: User, db: Session) -> int:
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_ATTEMPTS:
        user.lockout_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINS)
    db.commit()
    return user.failed_login_attempts


def _record_success(user: User, db: Session) -> None:
    user.failed_login_attempts = 0
    user.lockout_until = None
    user.last_login = datetime.now(timezone.utc)
    db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/login")
def admin_login(data: AdminLogin, db: Session = Depends(get_db)):
    """
    Secure admin login:
    - bcrypt password check
    - role == 'admin' enforced server-side
    - rate limiting with account lockout
    - real JWT on success
    """
    _INVALID = "Invalid credentials."

    user = db.query(User).filter(
        User.email == data.email.lower().strip()
    ).first()

    # Guard: user must exist AND be admin (same error message to prevent enumeration)
    if not user or user.role != "admin":
        raise HTTPException(status_code=401, detail=_INVALID)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is suspended. Contact your super admin.")

    _check_lockout(user)

    if not verify_password(data.password, user.hashed_password):
        attempts = _record_failure(user, db)
        if attempts >= MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Account locked for {LOCKOUT_MINS} minutes.",
            )
        remaining = MAX_ATTEMPTS - attempts
        raise HTTPException(
            status_code=401,
            detail=f"{_INVALID} {remaining} attempt(s) remaining before lockout.",
        )

    _record_success(user, db)

    token = create_access_token(data={"sub": user.email, "role": "admin"})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "admin",
        "user": {"name": user.full_name, "email": user.email},
    }


@router.post("/change-password")
def change_password(
    payload: ChangePasswordPayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Authenticated admins only. Verifies old password before setting new one."""
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match.")
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from your current password.")

    _validate_password(payload.new_password)

    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully."}


@router.post("/forgot-password")
def admin_forgot_password(
    payload: AdminForgotPassword,
    db: Session = Depends(get_db),
):
    """Issues a signed reset token for admin accounts only."""
    user = db.query(User).filter(
        User.email == payload.email.lower().strip(),
        User.role == "admin",
    ).first()

    # Always return same message (anti-enumeration)
    if not user:
        return {"message": "If that admin email exists, a reset link has been sent."}

    token = create_password_reset_token(email=user.email)

    # TODO: Send via email (SendGrid, Mailgun, etc.) before going to production.
    # Returning the token here is for local development only.
    return {
        "message": "If that admin email exists, a reset link has been sent.",
        "reset_token": token,  # REMOVE THIS LINE before production deployment
    }


@router.post("/reset-password")
def admin_reset_password(
    payload: AdminResetPassword,
    db: Session = Depends(get_db),
):
    """Validates a signed reset token and sets a new password."""
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    _validate_password(payload.new_password)

    email = verify_password_reset_token(payload.token)
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Reset link is invalid or has expired. Please request a new one.",
        )

    user = db.query(User).filter(User.email == email, User.role == "admin").first()
    if not user:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    user.hashed_password = get_password_hash(payload.new_password)
    user.failed_login_attempts = 0
    user.lockout_until = None
    db.commit()
    return {"message": "Password reset successfully. You can now log in."}


# ═════════════════════════════════════════════════════════════════════════════
# PROTECTED ADMIN ROUTES  (all require valid admin JWT via require_admin)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/stats")
def get_admin_stats(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total_users = db.query(User).count()
    return {
        "total_users": total_users,
        "total_listings": 0,    # wire to Listing model
        "total_messages": 0,    # wire to Message model
        "pending_reports": 0,   # wire to Report model
    }


@router.get("/analytics/growth")
def get_growth_data(_: User = Depends(require_admin)):
    return {
        "months":   ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
        "users":    [20, 45, 80, 110, 130, 150],
        "listings": [5, 12, 25, 33, 40, 45],
    }


@router.get("/users")
def get_all_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id":         u.id,
            "full_name":  u.full_name,
            "email":      u.email,
            "role":       u.role,
            "is_active":  u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
        }
        for u in users
    ]


@router.post("/users/{user_id}/suspend")
def toggle_suspend(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot suspend your own account.")
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"User {'suspended' if not user.is_active else 'reinstated'} successfully."}


@router.get("/all-listings")
def get_all_listings(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return []   # wire to Listing model


@router.patch("/listings/{listing_id}/approve")
def approve_listing(listing_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"message": f"Listing {listing_id} approved."}


@router.patch("/listings/{listing_id}/reject")
def reject_listing(listing_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"message": f"Listing {listing_id} rejected."}


@router.delete("/listings/{listing_id}")
def delete_listing(listing_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"message": f"Listing {listing_id} deleted."}


@router.get("/verifications")
def get_verification_queue(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    pending = db.query(User).filter(User.verification_status == "pending").all()
    return [
        {"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role}
        for u in pending
    ]


@router.post("/verifications/{user_id}/approve")
def approve_verification(user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.verification_status = "verified"
    user.is_verified = True
    db.commit()
    return {"message": "User verified successfully."}


@router.post("/verifications/{user_id}/reject")
def reject_verification(user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.verification_status = "rejected"
    db.commit()
    return {"message": "Verification rejected."}


@router.get("/reports")
def get_reports(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return []   # wire to Report model


@router.patch("/reports/{report_id}/dismiss")
def dismiss_report(report_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"message": f"Report {report_id} dismissed."}


@router.post("/announcements")
def send_announcement(payload: AnnouncementPayload, _: User = Depends(require_admin)):
    return {"message": f"Announcement '{payload.title}' queued for {payload.target}."}


@router.post("/settings/update")
def update_settings(payload: SettingsPayload, _: User = Depends(require_admin)):
    return {"message": "Settings updated."}
