"""
app/api/v1/endpoints/auth.py

Full auth router.

WHAT CHANGED IN THIS VERSION
----------------------------
1. Rate limiting is applied to every sensitive endpoint via the shared limiter
   from app.core.rate_limiter. Each decorated function now takes `request: Request`
   (slowapi needs it to read the client IP).
2. A lightweight failed-login lockout was added on top of the rate limit:
   after MAX_FAILED_ATTEMPTS wrong passwords for the same email+IP within
   LOCKOUT_WINDOW, further attempts are refused for LOCKOUT_SECONDS. This stops
   slow, targeted credential-stuffing that stays under the per-minute IP limit.

   NOTE: the lockout store is in-memory, so it is per-process. On a single
   Render web worker that's fine. If you scale to multiple workers, move this
   to Redis or a DB table â€” the interface (`_register_failure` / `_is_locked`
   / `_clear_failures`) is small and easy to swap.

Endpoints (behaviour otherwise unchanged):
  - POST /login
  - GET  /me
  - POST /register
  - POST /forgot-password
  - POST /reset-password
  - POST /google-login
"""
import hashlib
import logging
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.api.deps import create_access_token, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiter import (
    limiter,
    LOGIN_LIMIT,
    REGISTER_LIMIT,
    FORGOT_PASSWORD_LIMIT,
    RESET_PASSWORD_LIMIT,
)
from app.core.security import verify_password, get_password_hash, validate_password_strength
from app.core.sessions import create_session, maybe_alert_new_login
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.schemas.user import UserResponse, UserCreate
from app.utils.email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Authentication"])
log = logging.getLogger("findmynyumba.auth")

# Same vague message whether or not the email exists, so attackers can't
# use this endpoint to discover which emails are registered.
SAFE_RESET_RESPONSE = {
    "message": "If that email is registered, a password reset link has been sent."
}

# ---------------------------------------------------------------------------
# Failed-login lockout (in-memory; see module docstring for the scaling note)
# ---------------------------------------------------------------------------
MAX_FAILED_ATTEMPTS = 5          # wrong passwords before lockout
LOCKOUT_WINDOW      = 15 * 60    # seconds: attempts older than this are forgotten
LOCKOUT_SECONDS     = 15 * 60    # seconds the key stays locked once tripped

# key -> list[timestamp] of recent failures
_failures: dict[str, list[float]] = defaultdict(list)
# key -> unix time when the lock expires
_locked_until: dict[str, float] = {}


def _lock_key(email: str, request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{email.lower()}|{ip}"


def _is_locked(key: str) -> bool:
    until = _locked_until.get(key)
    if until and time.time() < until:
        return True
    if until:  # lock expired -> clean up
        _locked_until.pop(key, None)
    return False


def _register_failure(key: str) -> None:
    now = time.time()
    recent = [t for t in _failures[key] if now - t < LOCKOUT_WINDOW]
    recent.append(now)
    _failures[key] = recent
    if len(recent) >= MAX_FAILED_ATTEMPTS:
        _locked_until[key] = now + LOCKOUT_SECONDS
        _failures[key] = []  # reset the counter once locked


def _clear_failures(key: str) -> None:
    _failures.pop(key, None)
    _locked_until.pop(key, None)


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class GoogleLoginRequest(BaseModel):
    credential: str   # the ID token string Google Sign-In returns


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------
@router.post("/login")
@limiter.limit(LOGIN_LIMIT)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    key = _lock_key(body.email, request)
    if _is_locked(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please wait a few minutes and try again.",
        )

    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        _register_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended.",
        )

    _clear_failures(key)  # successful login wipes the failure record
    sid = create_session(db, user.id, request)
    maybe_alert_new_login(db, user, request, sid)
    token = create_access_token(
        data={"sub": str(user.id), "sid": str(sid)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


# Roles a self-registering user is allowed to choose. Anything else
# (especially "admin") is forced to "student" so nobody can grant
# themselves staff access by tampering with the request body.
SELF_SIGNUP_ROLES = {"student", "student_host", "landlord"}


@router.post("/register", response_model=UserResponse)
@limiter.limit(REGISTER_LIMIT)
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # SECURITY: never trust the role from the client. Admin/staff accounts
    # are created by an existing admin, never through public registration.
    safe_role = user_in.role if user_in.role in SELF_SIGNUP_ROLES else "student"

    new_user = User(
        email=user_in.email.lower(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=safe_role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ---------------------------------------------------------------------------
# Forgot password -> generate token, email a reset link
# ---------------------------------------------------------------------------
@router.post("/forgot-password")
@limiter.limit(FORGOT_PASSWORD_LIMIT)
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()

    # Always return the same response (don't leak whether the account exists).
    if not user:
        return SAFE_RESET_RESPONSE

    # Raw token goes in the email link; only its hash is stored.
    raw_token  = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    prt = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=60),
        used=False,
    )
    db.add(prt)
    db.commit()

    # FRONTEND_URL MUST be your real site in production, otherwise the link
    # points at localhost and nobody can use it.
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password.html?token={raw_token}"

    try:
        send_password_reset_email(user.email, user.full_name, reset_url)
    except Exception:
        # Don't expose email-provider failures to the caller; just log them.
        log.exception("Failed to send password reset email to %s", email)

    return SAFE_RESET_RESPONSE


# ---------------------------------------------------------------------------
# Reset password -> verify token, set new password
# ---------------------------------------------------------------------------
@router.post("/reset-password")
@limiter.limit(RESET_PASSWORD_LIMIT)
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()

    prt = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
        )
        .first()
    )

    # Frontend treats 400 as "invalid/expired" and shows the right screen.
    if not prt or prt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user = db.query(User).filter(User.id == prt.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset link.")

    user.hashed_password = get_password_hash(body.new_password)
    prt.used = True
    db.commit()

    # Security: a password reset kills all existing sessions, so a compromised
    # token cannot survive the reset. The user logs in fresh with the new password.
    _revoke_all(db, user.id)

    # A successful reset clears any active lockout for this account.
    _clear_failures(_lock_key(user.email, request))

    return {"message": "Password updated. You can now sign in with your new password."}


# ---------------------------------------------------------------------------
# Google login -> verify Google ID token, log in or create the user
# ---------------------------------------------------------------------------
@router.post("/google-login")
@limiter.limit(LOGIN_LIMIT)
def google_login(request: Request, body: GoogleLoginRequest, db: Session = Depends(get_db)):
    # Imported here so the rest of auth works even before google-auth is installed.
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google login is not configured on the server.")

    try:
        info = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,   # audience check â€” must match login.html
        )
    except ValueError:
        # Bad signature, wrong audience, or expired token.
        raise HTTPException(status_code=401, detail="Invalid Google sign-in. Please try again.")

    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Your Google email is not verified.")

    user = db.query(User).filter(User.email == email).first()

    if not user:
        # First time signing in with Google -> create an account.
        # They have no password they can type; we store a random unusable one.
        user = User(
            email=email,
            full_name=info.get("name", ""),
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            role="student",          # default role; adjust if you prefer
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended.")

    sid = create_session(db, user.id, request)
    maybe_alert_new_login(db, user, request, sid)
    token = create_access_token(
        data={"sub": str(user.id), "sid": str(sid)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
    }


# ---------------------------------------------------------------------------
# Session management endpoints (view / revoke / logout)
# ---------------------------------------------------------------------------
from app.models.user_session import UserSession as _UserSession
from app.core.sessions import revoke_session as _revoke_session, revoke_all_for_user as _revoke_all
from app.api.deps import get_current_session_id as _get_current_sid


@router.get("/sessions")
def list_sessions(
    current_user: User = Depends(get_current_user),
    current_sid: int = Depends(_get_current_sid),
    db: Session = Depends(get_db),
):
    """List the current user's active (non-revoked) sessions."""
    rows = (
        db.query(_UserSession)
          .filter(_UserSession.user_id == current_user.id, _UserSession.revoked == False)  # noqa: E712
          .order_by(_UserSession.created_at.desc())
          .all()
    )
    return [
        {
            "id": s.id,
            "is_current": s.id == current_sid,
            "user_agent": s.user_agent,
            "ip": s.ip,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_seen": s.last_seen.isoformat() if s.last_seen else None,
        }
        for s in rows
    ]


@router.post("/sessions/{session_id}/revoke")
def revoke_one_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a single session. You can only revoke your OWN sessions."""
    s = db.query(_UserSession).filter(_UserSession.id == session_id).first()
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")
    _revoke_session(db, session_id)
    return {"message": "Session revoked."}


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    current_sid: int = Depends(_get_current_sid),
    db: Session = Depends(get_db),
):
    """Revoke the current session (log out this device)."""
    if current_sid:
        _revoke_session(db, current_sid)
    return {"message": "Logged out."}


@router.post("/logout-all")
def logout_all_other(
    current_user: User = Depends(get_current_user),
    current_sid: int = Depends(_get_current_sid),
    db: Session = Depends(get_db),
):
    """Revoke all of the user's other sessions, keeping the current one."""
    n = _revoke_all(db, current_user.id, except_session_id=current_sid)
    return {"message": f"Logged out {n} other session(s).", "revoked_count": n}
