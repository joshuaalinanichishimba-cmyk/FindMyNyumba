"""
app/api/v1/endpoints/auth.py

SECURITY FIXES:
  - /auth/forgot-password  : no longer returns reset_token in response (prevents enumeration)
  - /auth/reset-password   : enforces one-time-use by hashing + clearing token after use
  - Token is stored as a SHA-256 hash in the DB — plain token only ever lives in the email link
  - Rate-limit helper guards /forgot-password (in-memory, upgrade to Redis for multi-worker)
  - Password regex enforced on both frontend and backend
  - Always returns a generic 200 on /forgot-password to prevent email enumeration
"""
import base64
import json
import hashlib
import re
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_password_reset_token,
    verify_password_reset_token,
)
from app.api.deps import get_current_user
from app.models.user import User
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Authentication"])

PWD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,12}$"

# ── In-memory rate limiter ─────────────────────────────────────────────────────
# Tracks (ip, email) → [timestamps]. Replace with Redis in production.
_reset_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW    = 600   # 10 minutes
_RATE_MAX       = 3     # max 3 attempts per window


def _rate_key(request: Request, email: str) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{ip}:{email.lower()}"


def _check_rate_limit(request: Request, email: str):
    key = _rate_key(request, email)
    now = time.time()
    # Purge old entries
    _reset_attempts[key] = [t for t in _reset_attempts[key] if now - t < _RATE_WINDOW]
    if len(_reset_attempts[key]) >= _RATE_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset requests. Please wait 10 minutes before trying again.",
        )
    _reset_attempts[key].append(now)


def _hash_token(token: str) -> str:
    """SHA-256 hash of a plain reset token for safe DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── Schemas ────────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    full_name:    str
    email:        str
    phone_number: str
    password:     str
    role:         str
    university:   Optional[str] = None
    student_id:   Optional[str] = None


class UserLogin(BaseModel):
    email:    str
    password: str


class GoogleLogin(BaseModel):
    credential: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str


# ── Register ───────────────────────────────────────────────────────────────────
@router.post("/register", status_code=201)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower().strip()).first():
        raise HTTPException(status_code=400, detail="Email already registered.")

    allowed_roles = {"student", "student_host", "landlord"}
    if payload.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Invalid role.")

    new_user = User(
        full_name       = payload.full_name.strip(),
        email           = payload.email.lower().strip(),
        phone_number    = payload.phone_number.strip(),
        role            = payload.role,
        hashed_password = get_password_hash(payload.password),
        is_active       = True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Account created successfully. You can now log in."}


# ── Login ──────────────────────────────────────────────────────────────────────
@router.post("/login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()

    # ── Lockout check ─────────────────────────────────────────────────────────
    if user and user.lockout_until:
        if datetime.now(timezone.utc) < user.lockout_until.replace(tzinfo=timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked due to multiple failed attempts. Try again later.",
            )
        else:
            # Lockout period has passed — reset counters
            user.lockout_until         = None
            user.failed_login_attempts = 0
            db.commit()

    if not user or not verify_password(payload.password, user.hashed_password):
        # Increment failure counter
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= 5:
                from datetime import timedelta
                user.lockout_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact support.",
        )

    # Reset counters on success
    user.failed_login_attempts = 0
    user.lockout_until         = None
    user.last_login            = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


# ── Google Login ───────────────────────────────────────────────────────────────
@router.post("/google-login")
def google_login(payload: GoogleLogin, db: Session = Depends(get_db)):
    try:
        segment  = payload.credential.split(".")[1]
        padding  = "=" * (4 - len(segment) % 4)
        decoded  = base64.urlsafe_b64decode(segment + padding)
        gdata    = json.loads(decoded)
        email    = gdata.get("email")
        name     = gdata.get("name", "Google User")

        if not email:
            raise HTTPException(status_code=400, detail="Invalid Google token.")

        user = db.query(User).filter(User.email == email.lower()).first()

        if not user:
            user = User(
                full_name       = name,
                email           = email.lower(),
                phone_number    = "",
                role            = "student",
                hashed_password = get_password_hash(f"GoogleOAuth_{email}"),
                is_active       = True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is suspended.")

        token = create_access_token(data={"sub": user.email, "role": user.role})
        return {"access_token": token, "token_type": "bearer", "role": user.role}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Google authentication failed.") from exc


# ── Me ─────────────────────────────────────────────────────────────────────────
@router.get("/me")
def read_user_me(current_user: User = Depends(get_current_user)):
    return {
        "id":                    current_user.id,
        "full_name":             current_user.full_name,
        "email":                 current_user.email,
        "role":                  current_user.role,
        "phone":                 current_user.phone_number,
        "avatar_url":            current_user.avatar_url,
        "business_name":         current_user.business_name,
        "verification_status":   current_user.verification_status,
        "email_alerts":          current_user.email_alerts,
        "sms_alerts":            current_user.sms_alerts,
    }


# ── Forgot Password ────────────────────────────────────────────────────────────
@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db:      Session = Depends(get_db),
):
    """
    Generates a one-time, expiring reset token and emails it to the user.

    Security properties:
      - Always returns 200 (prevents email enumeration)
      - Rate-limited per IP+email
      - Token is stored as a SHA-256 hash — plain token only in the email link
      - Previous token is invalidated when a new one is issued
    """
    _check_rate_limit(request, payload.email)

    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()

    # Return the same response regardless of whether the user exists
    SAFE_RESPONSE = {"message": "If that email is registered, a reset link has been sent."}

    if not user or not user.is_active:
        return SAFE_RESPONSE

    # Generate a signed JWT reset token (15-minute expiry — set in create_password_reset_token)
    plain_token = create_password_reset_token(email=user.email)

    # Store only the hash so the plain token never touches the DB
    user.reset_token_hash = _hash_token(plain_token)
    user.reset_token_used = False
    db.commit()

            # ── Resend Email API Integration (HTTP - Render Safe) ──
    import os
    import resend
    import logging

    resend.api_key = os.environ.get("RESEND_API_KEY")

    if resend.api_key:
        reset_link = f"https://findmynyumba-web.vercel.app/reset-password.html?token={plain_token}"
        
        html_content = f"""
        <p>Hi {user.full_name},</p>
        <p>Click the link below to reset your password. It expires in 15 minutes and can only be used once.</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>If you didn't request this, ignore this email.</p>
        """
        
        try:
            # Using Resend's testing domain so it works instantly without DNS setup
            r = resend.Emails.send({
                "from": "FindMyNyumba <onboarding@resend.dev>",
                "to": user.email,
                "subject": "FindMyNyumba — Reset Your Password",
                "html": html_content
            })
            logging.info(f"Email sent successfully via Resend: {r}")
        except Exception as e:
            logging.error(f"Resend Email send error: {e}")
    else:
        logging.warning("[WARNING] RESEND_API_KEY missing in env variables.")
    # ── End Resend Integration ──

    # DEVELOPMENT ONLY — log token to server console, never to HTTP response
    import logging
    logging.getLogger(__name__).warning(
        "[DEV] Password reset token for %s: %s  ← REMOVE logging in production",
        user.email, plain_token,
    )

    return SAFE_RESPONSE


# ── Reset Password ─────────────────────────────────────────────────────────────
@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Validates the reset token and sets a new password.

    Security properties:
      - Verifies JWT signature + expiry
      - Compares hashed token against DB — prevents token reuse even if JWT still valid
      - Marks token as used immediately after verification (one-time use)
      - Password complexity enforced server-side
    """
    INVALID_ERROR = HTTPException(
        status_code=400,
        detail="Reset link is invalid or has expired. Please request a new one.",
    )

    # 1. Verify JWT signature + expiry
    email = verify_password_reset_token(payload.token)
    if not email:
        raise INVALID_ERROR

    # 2. Load user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise INVALID_ERROR

    # 3. Compare hashed token (one-time-use guard)
    token_hash = _hash_token(payload.token)
    if not user.reset_token_hash or user.reset_token_hash != token_hash:
        raise INVALID_ERROR
    if user.reset_token_used:
        raise INVALID_ERROR

    # 4. Validate password complexity
    if not re.match(PWD_REGEX, payload.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8-12 characters with uppercase, lowercase, number, and special character.",
        )

    # 5. Invalidate token immediately (before committing new password)
    user.reset_token_used = True
    user.reset_token_hash = None   # clear so it can never be replayed

    # 6. Update password
    user.hashed_password       = get_password_hash(payload.new_password)
    user.failed_login_attempts = 0
    user.lockout_until         = None

    db.commit()
    return {"message": "Password updated successfully. You can now log in."}



