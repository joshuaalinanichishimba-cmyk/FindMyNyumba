"""
app/api/deps.py

Shared FastAPI dependencies:
  - get_current_user  : decode JWT, return User ORM object
  - create_access_token : create signed JWT

This was referenced in all endpoint files but never provided in the source files.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.core.sessions import is_session_active

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Token creation ─────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── JWT → User dependency ──────────────────────────────────────────────────────

def get_current_user(
    token: str     = Depends(oauth2_scheme),
    db: Session    = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended.",
        )

    sid = payload.get("sid")
    if not is_session_active(db, int(sid) if sid else None):
        raise credentials_exception

    return user


def get_current_session_id(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sid = payload.get("sid")
        return int(sid) if sid else None
    except JWTError:
        return None
