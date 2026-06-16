"""
app/core/security.py
Password hashing and JWT creation utilities.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long.")
    if password.isalpha() or password.isdigit():
        raise ValueError("Password must include both letters and numbers.")
    if password.lower() in {"password", "password1", "password123", "12345678", "qwerty123", "findmynyumba"}:
        raise ValueError("That password is too common - please choose another.")
    return password


def validate_password_strength(password: str) -> str:
    """Reject weak passwords. Raises ValueError. Shared by register + reset."""
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long.")
    if password.isalpha() or password.isdigit():
        raise ValueError("Password must include both letters and numbers.")
    if password.lower() in {
        "password", "password1", "password123",
        "12345678", "123456789", "1234567890",
        "qwerty123", "findmynyumba",
    }:
        raise ValueError("That password is too common - please choose another.")
    return password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_password_reset_token(email: str) -> str:
    """Short-lived token for password reset (1 hour)."""
    return create_access_token(
        data={"sub": email, "type": "password_reset"},
        expires_delta=timedelta(hours=1),
    )


def verify_password_reset_token(token: str) -> Optional[str]:
    """Returns email if valid reset token, else None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("sub")
    except Exception:
        return None
