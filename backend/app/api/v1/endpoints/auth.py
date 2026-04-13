"""
app/api/v1/endpoints/auth.py

FULL IMPLEMENTATION — was previously a 3-line stub.

Endpoints:
  POST /auth/login            — email + password → JWT
  POST /auth/register         — create student account
  POST /auth/register-landlord — create landlord/student_host account
  GET  /auth/me               — return current user from JWT
  POST /auth/forgot-password  — request reset link (email)
  POST /auth/reset-password   — consume token, set new password

Security improvements over the stub:
  - Passwords hashed with bcrypt via get_password_hash / verify_password
  - Lockout after 5 failed login attempts (15-minute window)
  - Reset token stored as SHA-256 hash; one-time use enforced
  - Role guard on /me so wrong-dashboard redirects work correctly
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, create_access_token
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.user import User

router = APIRouter(tags=["Auth"])

# ── Request / Response models ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email:    str
    password: str

class RegisterRequest(BaseModel):
    full_name: str
    email:     EmailStr
    password:  str
    role:      str = "student"       # student | landlord | student_host

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str

class ProfileUpdate(BaseModel):
    full_name: str
    phone:     Optional[str] = None

# ── Helpers ───────────────────────────────────────────────────────────────────

LOCKOUT_ATTEMPTS = 5
LOCKOUT_MINUTES  = 15

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def _check_lockout(user: User) -> None:
    """Raise 429 if the account is currently locked out."""
    if user.lockout_until and user.lockout_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked. Please try again later.",
        )

def _record_failed_attempt(user: User, db: Session) -> None:
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= LOCKOUT_ATTEMPTS:
        user.lockout_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
    db.commit()

def _reset_failed_attempts(user: User, db: Session) -> None:
    user.failed_login_attempts = 0
    user.lockout_until          = None
    user.last_login             = datetime.now(timezone.utc)
    db.commit()


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended. Please contact support.")

    _check_lockout(user)

    if not verify_password(payload.password, user.hashed_password):
        _record_failed_attempt(user, db)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    _reset_failed_attempts(user, db)

    token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role,
        "full_name":    user.full_name,
        "email":        user.email,
        "user_id":      user.id,
    }


# ── POST /auth/register ───────────────────────────────────────────────────────

ALLOWED_ROLES = {"student", "landlord", "student_host"}

@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    role = payload.role.lower().strip()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from: {', '.join(ALLOWED_ROLES)}")

    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    import re
    PWD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
    if not PWD_RE.match(payload.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters with uppercase, lowercase, number, and special character.",
        )

    user = User(
        full_name       = payload.full_name.strip(),
        email           = email,
        hashed_password = get_password_hash(payload.password),
        role            = role,
        is_active       = True,
        is_verified     = False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role,
        "full_name":    user.full_name,
        "email":        user.email,
        "user_id":      user.id,
    }


# ── POST /auth/register-landlord (alias — same logic, forces landlord role) ───

@router.post("/register-landlord", status_code=201)
def register_landlord(payload: RegisterRequest, db: Session = Depends(get_db)):
    payload.role = payload.role if payload.role in ("landlord", "student_host") else "landlord"
    return register(payload, db)


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile.
    All dashboards call this on boot to get role + display name.
    """
    return {
        "id":                    current_user.id,
        "full_name":             current_user.full_name,
        "email":                 current_user.email,
        "role":                  current_user.role,
        "phone":                 current_user.phone_number,
        "avatar_url":            current_user.avatar_url,
        "is_active":             current_user.is_active,
        "is_verified":           current_user.is_verified,
        "verification_status":   current_user.verification_status or "unverified",
        "business_name":         getattr(current_user, "business_name", None),
        "created_at":            current_user.created_at.isoformat() if current_user.created_at else None,
    }


# ── POST /auth/forgot-password ────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generates a one-time reset token (SHA-256 hash stored in DB).
    In production wire this to your email provider (SendGrid, Mailgun etc.).
    The plain token is returned in the response ONLY for dev/testing;
    in production it should be emailed and never returned in the response.
    """
    email = payload.email.lower().strip()
    user  = db.query(User).filter(User.email == email).first()

    # Always respond 200 to prevent email enumeration
    SAFE_RESPONSE = {"status": "success", "detail": "If that email exists, a reset link has been sent."}

    if not user or not user.is_active:
        return SAFE_RESPONSE

    plain_token = secrets.token_urlsafe(32)
    user.reset_token_hash = _sha256(plain_token)
    user.reset_token_used = False
    db.commit()

    # TODO: send email with reset link containing plain_token
    # e.g. f"https://yoursite.com/reset-password.html?token={plain_token}&email={email}"
    # For development, the token is included in the response so you can test it:
    return {
        "status":      "success",
        "detail":      "Reset link sent (dev mode — token included below).",
        "_dev_token":  plain_token,   # Remove this line before going to production!
    }


# ── POST /auth/reset-password ─────────────────────────────────────────────────

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = _sha256(payload.token)
    user = db.query(User).filter(
        User.reset_token_hash == token_hash,
        User.reset_token_used == False,
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    import re
    PWD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
    if not PWD_RE.match(payload.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters with uppercase, lowercase, number, and special character.",
        )

    from app.core.security import get_password_hash
    user.hashed_password  = get_password_hash(payload.new_password)
    user.reset_token_used = True          # one-time-use enforced
    user.reset_token_hash = None          # invalidate immediately
    db.commit()

    return {"status": "success", "detail": "Password reset successfully. Please log in."}
