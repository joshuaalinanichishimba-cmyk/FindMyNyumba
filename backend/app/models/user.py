"""
app/models/user.py

ADDED FIELDS:
  - reset_token_hash       : SHA-256 hash of the most recently issued reset token.
                             Storing the hash (not the plain token) means a DB breach
                             cannot be used to reset passwords.
  - reset_token_used       : Boolean flag — True after the token has been consumed.
                             Enforces one-time-use regardless of JWT expiry.
  - reset_token_expires_at : UTC datetime when the active token expires.
                             Used by the duplicate-token guard so an expired (unused)
                             token does not permanently block new reset requests.

After adding these columns run:
    alembic revision --autogenerate -m "add password reset token fields"
    alembic upgrade head

Or for a quick dev cycle (destroys data):
    DROP TABLE users; restart uvicorn (SQLAlchemy recreates the table).
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__  = "users"
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

    # ── Login tracking ────────────────────────────────────────────────────────
    last_login            = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    lockout_until         = Column(DateTime(timezone=True), nullable=True)

    # ── Password reset (one-time-use, hash-only storage) ──────────────────────
    # Plain token is NEVER stored — only its SHA-256 hash.
    # reset_token_used       : True the moment the token is consumed.
    # reset_token_expires_at : When the token expires (UTC). Allows the duplicate-
    #                          token guard to distinguish "active token" from
    #                          "expired unused token", preventing permanent lockout.
    reset_token_hash       = Column(String,                  nullable=True)
    reset_token_used       = Column(Boolean, default=False,  nullable=False)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    listings = relationship("Listing", back_populates="owner")
