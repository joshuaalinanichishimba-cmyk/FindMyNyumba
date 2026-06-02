"""
app/models/listing.py

FIX: status default changed from "active" → "pending".
     All new listings must go through admin review before going live.

ADDED (Student Host Phase):
  - nearest_institution : which university/college the bedspace is near
  - availability_status : "available" | "taken" (independent of admin approval status)
  - total_spots         : how many bedspaces the host is offering in this listing
  - available_spots     : how many are still open (≤ total_spots)
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
    status      = Column(String, default="pending", nullable=False, index=True)

    # Boost: when True, listing appears at top of browse results
    is_boosted  = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # FK to owner (landlord or student_host)
    owner_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner       = relationship("User", back_populates="listings")

    # ── Student Host bedspace fields ──────────────────────────────────────────
    # Which institution the bedspace is near (e.g. "UNZA", "CBU")
    nearest_institution = Column(String, nullable=True, index=True)

    # Availability toggle — host can mark a listing as taken without deleting
    # This is separate from admin "status" (pending/active/rejected).
    # "available" means spots are open; "taken" means fully occupied.
    availability_status = Column(String, default="available", nullable=False)

    # Spot management — how many bedspaces in this listing
    total_spots     = Column(Integer, default=1, nullable=False)
    available_spots = Column(Integer, default=1, nullable=False)

    # ── Multi-media (NEW) ─────────────────────────────────────────────────────
    # Ordered photos/videos. selectin avoids N+1 by batch-loading media.
    media = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="ListingMedia.position",
        lazy="selectin",
    )

    @property
    def cover_url(self):
        """Best single URL: flagged cover -> first media -> legacy image_url."""
        if self.media:
            cover = next((m for m in self.media if m.is_cover), None)
            return (cover or self.media[0]).media_url
        return self.image_url
