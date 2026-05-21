"""
app/models/saved_property.py - FIXED VERSION

FIXES:
- Column renamed: property_id → listing_id (was breaking saved listings query)
- Added unique constraint: one save per user per listing
- Matches student_endpoints.py query: SavedProperty.listing_id
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from datetime import datetime
from app.core.database import Base


class SavedProperty(Base):
    __tablename__ = "saved_properties"
    __table_args__ = (
        UniqueConstraint('user_id', 'listing_id', name='uq_user_listing'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # FIXED: Changed from property_id to listing_id to match queries
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
