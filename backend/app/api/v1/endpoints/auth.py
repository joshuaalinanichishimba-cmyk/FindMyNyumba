"""
app/api/v1/endpoints/auth.py

Full auth router. Adds the THREE endpoints the frontend was already calling
but that did not exist on the backend:
  - POST /forgot-password   (forgot-password.html)
  - POST /reset-password    (reset-password.html)
  - POST /google-login      (login.html  Google Sign-In)

Existing /login, /me, /register are unchanged in behaviour.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import create_access_token, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.schemas.user import UserResponse, UserCreate
from app.utils.email import send_password_reset_email

router = APIRouter()
log = logging.getLogger("findmynyumba.auth")

# Same vague message whether or not the email exists, so attackers can't
# use this endpoint to discover which emails are registered.
SAFE_RESET_RESPONSE = {
    "message": "If that email is registered, a password reset link has been sent."
}


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


class GoogleLoginRequest(BaseModel):
    credential: str   # the ID token string Google Sign-In returns


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------
@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended.",
        )
    token = create_access_token(
        data={"sub": str(user.id)},
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


@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user_in.email.lower(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ---------------------------------------------------------------------------
# NEW: Forgot password  -> generate token, email a reset link
# ---------------------------------------------------------------------------
@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
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

    # FRONTEND_URL MUST be your real site in production, e.g.
    # https://find-my-nyumba-original.vercel.app  â€” otherwise the link
    # points at localhost and nobody can use it.
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password.html?token={raw_token}"

    try:
        send_password_reset_email(user.email, user.full_name, reset_url)
    except Exception:
        # Don't expose email-provider failures to the caller; just log them.
        log.exception("Failed to send password reset email to %s", email)

    return SAFE_RESET_RESPONSE


# ---------------------------------------------------------------------------
# NEW: Reset password  -> verify token, set new password
# ---------------------------------------------------------------------------
@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
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

    return {"message": "Password updated. You can now sign in with your new password."}


# ---------------------------------------------------------------------------
# NEW: Google login  -> verify Google ID token, log in or create the user
# ---------------------------------------------------------------------------
@router.post("/google-login")
def google_login(body: GoogleLoginRequest, db: Session = Depends(get_db)):
    # Imported here so the rest of auth works even before google-auth is installed.
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google login is not configured on the server.")

    try:
        info = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,   # this is the audience check â€” must match login.html
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

    token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
    }

