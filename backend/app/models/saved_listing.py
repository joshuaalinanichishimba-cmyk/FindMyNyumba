"""app/models/saved_listing.py - SavedListing model for student saved properties."""
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class SavedListing(Base):
    """Junction table for student saved listings.
    
    Ensures one row per (student_id, listing_id) pair.
    Persists across browser sessions and server restarts.
    """
    __tablename__ = "saved_listings"
    __table_args__ = (
        UniqueConstraint("student_id", "listing_id", name="uq_student_listing"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("User", foreign_keys=[student_id])
    listing = relationship("Listing", foreign_keys=[listing_id])
