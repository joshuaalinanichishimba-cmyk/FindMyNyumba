"""
app/models/user.py

ADDED FIELDS for security hardening:
  - last_login             : timestamp of last successful login
  - failed_login_attempts  : counter for rate limiting
  - lockout_until          : datetime until account is locked (NULL = not locked)

After adding these columns run:
    alembic revision --autogenerate -m "add login tracking fields"
    alembic upgrade head

Or, for a quick dev reset:
    DROP TABLE users; then restart uvicorn (SQLAlchemy recreates the table).
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id              = Column(Integer, primary_key=True, index=True)
    full_name       = Column(String, index=True)
    email           = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role            = Column(String, default="student")

    # Status
    is_active   = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # Profile
    phone_number = Column(String, nullable=True)
    avatar_url   = Column(String, nullable=True)

    # Landlord-specific
    business_name     = Column(String, nullable=True)
    business_location = Column(String, nullable=True)
    id_number         = Column(String, nullable=True)

    # Notification preferences
    email_alerts = Column(Boolean, default=True)
    sms_alerts   = Column(Boolean, default=False)

    # Verification workflow
    verification_status           = Column(String, default="unverified")
    verification_rejection_reason = Column(String, nullable=True)

    # ── Login tracking (NEW) ──────────────────────────────────────────────────
    last_login            = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    lockout_until         = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    listings = relationship("Listing", back_populates="owner")
