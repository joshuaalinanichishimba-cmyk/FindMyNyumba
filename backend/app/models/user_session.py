"""
app/models/user_session.py

One row per login session. The JWT carries this row's id as the `sid` claim;
get_current_user checks the session is still active on every request, so a
session can be revoked (logout, logout-all, password reset, suspension) even
though the JWT itself has not expired. This is what makes tokens revocable.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from app.core.database import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_agent = Column(String, nullable=True)
    ip         = Column(String, nullable=True)
    revoked    = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen  = Column(DateTime, default=datetime.utcnow, nullable=False)
