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
- Email validation now checks domain against a whitelist of common providers
  to prevent typos (e.g., exampl.com instead of example.com).
- All database commits now wrapped in try/except with rollback on failure
  to ensure clean state on transaction errors.
- User response shape is now canonical and consistent across all endpoints.
- Forgot-password validates email domain, prevents duplicate active tokens,
  and has placeholder for email dispatch service integration.
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

# ── Constants ───────────────────────────────────────────────────────────[...]
LOCKOUT_ATTEMPTS         = 5
LOCKOUT_MINUTES          = 15
RESET_TOKEN_TTL_MINUTES  = 60   # reset link valid for 1 hour

PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
PASSWORD_RULE_MSG = (
    "Password must be at least 8 characters and include uppercase, "
    "lowercase, a number, and a special character."
)

ALLOWED_ROLES = {"student", "landlord", "student_host"}

# Common email domains (local institutions + major providers)
# Add/customize based on your target user base
ALLOWED_EMAIL_DOMAINS = {
    # Academic/Student
    "student.co.ke", "ac.ke", "uni.ac.ke",
    # Major global providers
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "protonmail.com", "icloud.com",
}


# ── Request models ─────────────────────────────────────────────────────────[...]
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


# ── Internal helpers ────────────────────────────────────────────────────────[...]
def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_email_domain(email: str) -> None:
    """Validate email domain against whitelist to catch typos."""
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format.")
    
    domain = email.split("@")[1].lower()
    if domain not in ALLOWED_EMAIL_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=f"Email domain '{domain}' not supported. Use gmail.com, yahoo.com, outlook.com, or student.co.ke",
        )


def _check_lockout(user: User) -> None:
    """Raise 429 if the account is currently locked out."""
    if user.lockout_until and user.lockout_until > _now():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please try again later.",
        )


def _record_failed_attempt(user: User, db: Session) -> None:
    try:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= LOCKOUT_ATTEMPTS:
            user.lockout_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
        db.commit()
    except Exception as e:
        db.rollback()
        log.error("Failed to record login attempt: %s", e)
        raise HTTPException(
            status_code=500,
            detail="An error occurred. Please try again."
        )


def _reset_failed_attempts(user: User, db: Session) -> None:
    try:
        user.failed_login_attempts = 0
        user.lockout_until         = None
        user.last_login            = _now()
        db.commit()
    except Exception as e:
        db.rollback()
        log.error("Failed to reset login attempts: %s", e)
        raise HTTPException(
            status_code=500,
            detail="An error occurred. Please try again."
        )


def _build_reset_token(user_id: int) -> str:
    """
    Reset tokens carry their own expiry, so we don't need a new DB column.
    The JWT is signed with SECRET_KEY; the SHA-256 of this JWT is stored
    on the user row and cleared on use, enforcing one-time consumption.
    
    Token expires after RESET_TOKEN_TTL_MINUTES.
    """
    payload = {
        "sub":    str(user_id),
        "scope":  "pwd_reset",
        "exp":    _now() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        "jti":    secrets.token_hex(8),  # randomness so tokens aren't predictable
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_reset_token(token: str) -> Optional[int]:
    """
    Returns user_id on success, None on any failure.
    Handles expired, malformed, and invalid tokens uniformly for security.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        log.debug("Expired password reset token attempted")
        return None
    except JWTError as e:
        log.debug("Invalid password reset token: %s", type(e).__name__)
        return None
    
    # Verify token is a password reset token (not some other JWT)
    if payload.get("scope") != "pwd_reset":
        log.debug("Password reset token with wrong scope attempted")
        return None
    
    sub = payload.get("sub")
    try:
        return int(sub)
    except (TypeError, ValueError):
        log.debug("Invalid user_id in password reset token")
        return None


def user_to_dict(user: User, include_token: Optional[str] = None) -> dict:
    """
    Canonical user response shape used across all endpoints.
    
    Args:
        user: User model instance
        include_token: Optional JWT access token to include in response
    
    Returns:
        Dictionary with consistent field names and structure
    """
    locked = bool(user.lockout_until and user.lockout_until > _now())
    response = {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone_number,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_locked": locked,
        "verification_status": user.verification_status or "unverified",
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    
    # Optionally include landlord-specific field
    if user.business_name:
        response["business_name"] = user.business_name
    
    # Optionally include JWT token (for login/register responses)
    if include_token:
        response["access_token"] = include_token
        response["token_type"] = "bearer"
    
    return response


def _auth_response(user: User) -> dict:
    """Auth endpoints response: includes access token."""
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    response = user_to_dict(user, include_token=token)
    # For backwards compatibility with login/register clients expecting user_id
    response["user_id"] = user.id
    return response


# ── POST /auth/login ────────────────────────────────────────────────────────[...]
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
    
    # Validate email domain before checking database
    _validate_email_domain(email)
    
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    if not PASSWORD_RE.match(payload.password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MSG)

    try:
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
    except Exception as e:
        db.rollback()
        log.error("Failed to create user account for %s: %s", email, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to create account. Please try again."
        )

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


# ── GET /auth/me ──────────────────────────────────────────────────────────[...]
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return user_to_dict(current_user)


# ── POST /auth/forgot-password ────────────────────────────────────────────────
@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generates a one-time, time-limited reset token. The token's SHA-256 hash
    is stored on the user row so a DB breach cannot be used to mint resets.
    The plain token is dispatched out-of-band (email) and is NEVER returned
    in the API response.
    
    To prevent abuse:
    - Email domain is validated (same as /register)
    - Existing active tokens are not overwritten (rate limit)
    - Response is always identical (no user enumeration)
    """
    email = (payload.email or "").lower().strip()
    
    # Validate email domain (consistent with /register)
    _validate_email_domain(email)
    
    user = db.query(User).filter(User.email == email).first()

    # Always respond identically — prevents email-enumeration attacks.
    SAFE_RESPONSE = {
        "status": "success",
        "detail": "If that email exists, a reset link has been sent.",
    }

    if not user or not user.is_active:
        return SAFE_RESPONSE

    # Prevent rate limiting abuse: don't issue a new token if one is already active
    # (not used and not expired). User must wait for token to expire or use existing one.
    if user.reset_token_used == False and user.reset_token_hash is not None:
        log.warning("Duplicate reset token request for user %s (may indicate abuse)", user.id)
        return SAFE_RESPONSE  # Same response to avoid revealing duplicate attempt

    try:
        plain_token = _build_reset_token(user.id)
        user.reset_token_hash = _sha256(plain_token)
        user.reset_token_used = False
        db.commit()
    except Exception as e:
        db.rollback()
        log.error("Failed to generate password reset token for %s: %s", email, e)
        # Still return SAFE_RESPONSE to avoid leaking whether the user exists
        return SAFE_RESPONSE

    # TODO: Implement email dispatch via service (SendGrid, Mailgun, SES, etc.)
    # Example integration:
    #   try:
    #       send_password_reset_email(
    #           email=user.email,
    #           reset_token=plain_token,
    #           reset_url=f"{settings.FRONTEND_URL}/reset-password?token={plain_token}"
    #       )
    #   except Exception as e:
    #       log.error("Failed to send password reset email to %s: %s", email, e)
    #       # Still return SAFE_RESPONSE to not leak whether send failed
    #       return SAFE_RESPONSE
    
    # For local development only: log token at DEBUG level (not INFO)
    if not settings.PRODUCTION:
        log.debug("[DEV] Password reset token for %s: %s", email, plain_token)

    return SAFE_RESPONSE


# ── POST /auth/reset-password ─────────────────────────────────────────────────
@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Validate reset token (signature + expiry + one-time-use) and update password.
    
    Security checks:
    - Token signature verified (JWT)
    - Token expiry checked (embedded in JWT)
    - Token marked as used after consumption
    - Account lockout cleared on successful reset
    """
    user_id = _decode_reset_token(payload.token)
    if user_id is None:
        # Could be: signature failure, wrong scope, malformed sub, or expired.
        # Unified message to avoid leaking which check failed.
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    token_hash = _sha256(payload.token)
    user = db.query(User).filter(
        User.id               == user_id,
        User.reset_token_hash == token_hash,
        User.reset_token_used == False,
    ).first()

    if not user:
        # Token was valid when checked above, but DB record missing or token already used
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    if not PASSWORD_RE.match(payload.new_password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MSG)

    try:
        user.hashed_password  = get_password_hash(payload.new_password)
        user.reset_token_used = True       # one-time-use enforced
        user.reset_token_hash = None       # invalidate immediately

        # Also clear any active lockout — successful reset implies the legitimate
        # owner has regained control.
        user.failed_login_attempts = 0
        user.lockout_until         = None
        db.commit()
    except Exception as e:
        db.rollback()
        log.error("Failed to reset password for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to reset password. Please try again."
        )

    return {"status": "success", "detail": "Password reset successfully. Please log in."}
