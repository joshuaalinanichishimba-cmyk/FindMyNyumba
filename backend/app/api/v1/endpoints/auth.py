"""
app/api/v1/endpoints/auth.py

FIX: Added POST /auth/forgot-password and POST /auth/reset-password endpoints.
     These power the forgot-password.html flow that was linked but broken.
FIX: Canonical import from app.api.deps.
"""
import base64
import json
from fastapi import APIRouter, Depends, HTTPException, status
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


# ── Schemas ───────────────────────────────────────────────────────────────────
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


# ── Register ──────────────────────────────────────────────────────────────────
@router.post("/register", status_code=201)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower().strip()).first():
        raise HTTPException(status_code=400, detail="Email already registered.")

    allowed_roles = {"student", "student_host", "landlord"}
    if payload.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Invalid role. Must be student, student_host, or landlord.")

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


# ── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact support.",
        )

    token = create_access_token(data={"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


# ── Google Login ──────────────────────────────────────────────────────────────
@router.post("/google-login")
def google_login(payload: GoogleLogin, db: Session = Depends(get_db)):
    try:
        segment  = payload.credential.split(".")[1]
        padding  = "=" * (4 - len(segment) % 4)
        decoded  = base64.urlsafe_b64decode(segment + padding)
        gdata    = json.loads(decoded)

        email = gdata.get("email")
        name  = gdata.get("name", "Google User")

        if not email:
            raise HTTPException(status_code=400, detail="Invalid Google token: no email found.")

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


# ── Me ────────────────────────────────────────────────────────────────────────
@router.get("/me")
def read_user_me(current_user: User = Depends(get_current_user)):
    return {
        "id":            current_user.id,
        "full_name":     current_user.full_name,
        "email":         current_user.email,
        "role":          current_user.role,
        "phone":         current_user.phone_number,
        "avatar_url":    current_user.avatar_url,
        "business_name": current_user.business_name,
        "verification_status": current_user.verification_status,
        "email_alerts":  current_user.email_alerts,
        "sms_alerts":    current_user.sms_alerts,
    }


# ── Forgot Password ───────────────────────────────────────────────────────────
@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generates a password reset token.
    In production: email this token link to the user.
    For now: returns the token in the response for local testing.
    Replace with email integration (SendGrid, Mailgun, etc.) before launch.
    """
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()

    # Always return success to prevent email enumeration attacks
    if not user:
        return {"message": "If that email is registered, a reset link has been sent."}

    reset_token = create_password_reset_token(email=user.email)

    # TODO: Send reset_token via email instead of returning it here
    # For development: include token in response so frontend can test flow
    return {
        "message":     "If that email is registered, a reset link has been sent.",
        "reset_token": reset_token,  # REMOVE THIS LINE in production
    }


# ── Reset Password ────────────────────────────────────────────────────────────
@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Validates the reset token and sets a new password."""
    import re
    PWD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,12}$"

    email = verify_password_reset_token(payload.token)
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Reset link is invalid or has expired. Please request a new one.",
        )

    if not re.match(PWD_REGEX, payload.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8-12 characters with uppercase, lowercase, number, and special character.",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully. You can now log in."}
