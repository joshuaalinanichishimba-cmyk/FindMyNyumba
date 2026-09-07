"""
Blacklist — phone numbers, mobile-money / bank accounts, or email addresses
that FindMyNyumba has flagged as fraudulent. Used by:
  - the public safety lookup (GET /safety/verify-landlord) to warn students, and
  - the admin trust module to add/remove entries.

Adding an entry can auto-flag active listings whose owner matches the value.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class Blacklist(Base):
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, index=True)

    entity_type = Column(String, nullable=False, index=True)   # phone | account | email
    value       = Column(String, nullable=False, index=True)   # normalised identifier
    reason      = Column(String, nullable=True)                 # short offense label
    admin_note  = Column(Text,   nullable=True)

    is_active   = Column(Boolean, default=True, index=True)     # False = revoked
    created_by  = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
