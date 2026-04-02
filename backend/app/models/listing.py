"""
app/models/listing.py

FIX: status default changed from "active" → "pending".
     All new listings must go through admin review before going live.
     The previous default of "active" would have made any listing created
     directly via the ORM (e.g. in tests or scripts) bypass moderation.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {'extend_existing': True}

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    price       = Column(Float, nullable=False)
    location    = Column(String, nullable=False, index=True)
    image_url   = Column(String, nullable=True)

    # Workflow: pending | active | rejected
    # FIX: default changed from "active" to "pending" — all new listings
    # require admin approval before appearing in browse results.
    status      = Column(String, default="pending", nullable=False, index=True)

    # Boost: when True, listing appears at top of browse results
    is_boosted  = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # FK to owner (landlord or student_host)
    owner_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner       = relationship("User", back_populates="listings")
