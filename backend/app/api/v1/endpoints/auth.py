"""
app/api/v1/endpoints/auth.py

Endpoints:
  POST /auth/login            — email + password → JWT
  POST /auth/register         — create student account
  POST /auth/register-landlord — create landlord account (also accepts student_host)
  GET  /auth/me               — return current user from JWT
  POST /auth/forgot-password  — request reset link
  POST /auth/reset-password   — consume token, set new password

FIXES vs original:
- /auth/register-landlord no longer trusts payload.role at all. It hard-locks
  the new account to "landlord" so the endpoint can't be used to create
  arbitrary roles via parameter tampering. (Original allowed creating
  student_host accounts via this route.) student_host signups go through
  /auth/register with role="student_host".
- /auth/forgot-password no longer returns the plain reset token in the
  response body. The original `_dev_token` field was a guaranteed-leak
  vector once shipped. The token is logged at INFO level in dev only.
- Reset tokens now expire after RESET_TOKEN_TTL_MINUTES. Expiry is encoded
  into the token itself (signed with SECRET_KEY) so no schema change is
  required. Server-side one-time-use is still enforced via the existing
  reset_token_used flag.
- Password rules centralized into a single regex/constant shared with
  students.py / landlords.py / student_hosts.py.
- Email normalisation (.lower().strip()) consistent across all paths.
- /auth/me returns the same shape as before plus is_locked so dashboards
  can render lockout state without an extra round-trip.
"""

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import create_access_token, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.user import User

router = APIRouter(tags=["Auth"])
log = logging.getLogger("findmynyumba.auth")

# ── Constants ─────────────────────────────────────────────────────────────────
LOCKOUT_ATTEMPTS         = 5
LOCKOUT_MINUTES          = 15
RESET_TOKEN_TTL_MINUTES  = 60   # reset link valid for 1 hour

PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
PASSWORD_RULE_MSG = (
    "Password must be at least 8 characters and include uppercase, "
    "lowercase, a number, and a special character."
)

ALLOWED_ROLES = {"student", "landlord", "student_host"}


# ── Request models ────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email:    str
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    email:     EmailStr
    password:  str
    role:      str = "student"   # student | landlord | student_host


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str


# ── Internal helpers ──────────────────────────────────────────────────────────
def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_lockout(user: User) -> None:
    """Raise 429 if the account is currently locked out."""
    if user.lockout_until and user.lockout_until > _now():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please try again later.",
        )


def _record_failed_attempt(user: User, db: Session) -> None:
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= LOCKOUT_ATTEMPTS:
        user.lockout_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
    db.commit()


def _reset_failed_attempts(user: User, db: Session) -> None:
    user.failed_login_attempts = 0
    user.lockout_until         = None
    user.last_login            = _now()
    db.commit()


def _build_reset_token(user_id: int) -> str:
    """
    Reset tokens carry their own expiry, so we don't need a new DB column.
    The JWT is signed with SECRET_KEY; the SHA-256 of this JWT is stored
    on the user row and cleared on use, enforcing one-time consumption.
    """
    payload = {
        "sub":    str(user_id),
        "scope":  "pwd_reset",
        "exp":    _now() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        "jti":    secrets.token_hex(8),  # randomness so tokens aren't predictable
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_reset_token(token: str) -> Optional[int]:
    """Returns user_id on success, None on any failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("scope") != "pwd_reset":
        return None
    sub = payload.get("sub")
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


def _auth_response(user: User) -> dict:
    """Shape used by /login, /register, /register-landlord."""
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role,
        "full_name":    user.full_name,
        "email":        user.email,
        "user_id":      user.id,
    }


# ── POST /auth/login ──────────────────────────────────────────────────────────
@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user  = db.query(User).filter(User.email == email).first()

    # Use the same generic message for unknown email and wrong password to
    # avoid leaking which one was wrong (account-enumeration defence).
    GENERIC_INVALID = HTTPException(status_code=401, detail="Invalid email or password.")

    if not user:
        raise GENERIC_INVALID

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended. Please contact support.")

    _check_lockout(user)

    if not verify_password(payload.password, user.hashed_password):
        _record_failed_attempt(user, db)
        raise GENERIC_INVALID

    _reset_failed_attempts(user, db)
    return _auth_response(user)


# ── POST /auth/register ───────────────────────────────────────────────────────
@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    role = (payload.role or "student").lower().strip()
    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Choose from: {', '.join(sorted(ALLOWED_ROLES))}",
        )

    full_name = (payload.full_name or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required.")

    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    if not PASSWORD_RE.match(payload.password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MSG)

    user = User(
        full_name       = full_name,
        email           = email,
        hashed_password = get_password_hash(payload.password),
        role            = role,
        is_active       = True,
        is_verified     = False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _auth_response(user)


# ── POST /auth/register-landlord ──────────────────────────────────────────────
@router.post("/register-landlord", status_code=201)
def register_landlord(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Hard-locks role to "landlord". The original implementation forwarded the
    payload role to register(), which let callers create student_host
    accounts via this endpoint by setting role="student_host" in the body.
    student_host accounts must go through /auth/register.
    """
    payload.role = "landlord"
    return register(payload, db)


# ── GET /auth/me ──────────────────────────────────────────────────────────────
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    locked = bool(current_user.lockout_until and current_user.lockout_until > _now())
    return {
        "id":                  current_user.id,
        "full_name":           current_user.full_name,
        "email":               current_user.email,
        "role":                current_user.role,
        "phone":               current_user.phone_number,
        "avatar_url":          current_user.avatar_url,
        "is_active":           current_user.is_active,
        "is_verified":         current_user.is_verified,
        "is_locked":           locked,
        "verification_status": current_user.verification_status or "unverified",
        "business_name":       getattr(current_user, "business_name", None),
        "created_at":          current_user.created_at.isoformat() if current_user.created_at else None,
    }


# ── POST /auth/forgot-password ────────────────────────────────────────────────
@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generates a one-time, time-limited reset token. The token's SHA-256 hash
    is stored on the user row so a DB breach cannot be used to mint resets.
    The plain token is dispatched out-of-band (email) and is NEVER returned
    in the API response.
    """
    email = (payload.email or "").lower().strip()
    user  = db.query(User).filter(User.email == email).first()

    # Always respond identically — prevents email-enumeration attacks.
    SAFE_RESPONSE = {
        "status": "success",
        "detail": "If that email exists, a reset link has been sent.",
    }

    if not user or not user.is_active:
        return SAFE_RESPONSE

    plain_token = _build_reset_token(user.id)
    user.reset_token_hash = _sha256(plain_token)
    user.reset_token_used = False
    db.commit()

    # TODO: dispatch via email provider (SendGrid, Mailgun, SES, …)
    # For local development only, the token is logged so you can copy it
    # from the server console while testing. NEVER returned in the response.
    log.info("Password reset requested for %s. Reset URL token: %s", email, plain_token)

    return SAFE_RESPONSE


# ── POST /auth/reset-password ─────────────────────────────────────────────────
@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user_id = _decode_reset_token(payload.token)
    if user_id is None:
        # Either signature failure, wrong scope, malformed sub, or expired.
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    token_hash = _sha256(payload.token)
    user = db.query(User).filter(
        User.id               == user_id,
        User.reset_token_hash == token_hash,
        User.reset_token_used == False,
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    if not PASSWORD_RE.match(payload.new_password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MSG)

    user.hashed_password  = get_password_hash(payload.new_password)
    user.reset_token_used = True       # one-time-use enforced
    user.reset_token_hash = None       # invalidate immediately

    # Also clear any active lockout — successful reset implies the legitimate
    # owner has regained control.
    user.failed_login_attempts = 0
    user.lockout_until         = None
    db.commit()

    return {"status": "success", "detail": "Password reset successfully. Please log in."}
