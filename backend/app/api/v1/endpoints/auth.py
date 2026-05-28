"""
app/api/v1/endpoints/auth.py
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
from app.utils.email import send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters long.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must contain at least one letter and one number.")

def _validate_phone_number(phone: str) -> None:
    pattern = re.compile(r"^\+?[1-9]\d{6,14}$")
    if not pattern.match(re.sub(r"[\s\-()]", "", phone)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid phone number format.")

def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    _validate_password_strength(payload.password)
    if payload.phone_number:
        _validate_phone_number(payload.phone_number)
    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("New user registered (pending activation): %s", user.email)
    return {"message": "Registration successful. Please check your email to activate your account."}

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")
    access_token = create_access_token(subject=str(user.id))
    logger.info("User logged in: %s", user.email)
    return TokenResponse(access_token=access_token)

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/password-reset", status_code=status.HTTP_204_NO_CONTENT)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return
    raw_token = secrets.token_urlsafe(32)
    user.password_reset_token = _hash_reset_token(raw_token)
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()
    try:
        send_password_reset_email(email=user.email, token=raw_token)
    except Exception:
        logger.exception("Failed to send password-reset email to %s", user.email)

@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    hashed = _hash_reset_token(payload.token)
    user = db.query(User).filter(User.password_reset_token == hashed).first()
    invalid_exc = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired password reset token.")
    if not user:
        raise invalid_exc
    if user.password_reset_expires is None or datetime.now(timezone.utc) > user.password_reset_expires:
        raise invalid_exc
    _validate_password_strength(payload.new_password)
    user.hashed_password = get_password_hash(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()
    logger.info("Password reset completed for: %s", user.email)
