"""
app/models/listing.py

FIX: status default changed from "active" â†’ "pending".
     All new listings must go through admin review before going live.

ADDED (Student Host Phase):
  - nearest_institution : which university/college the bedspace is near
  - availability_status : "available" | "taken" (independent of admin approval status)
  - total_spots         : how many bedspaces the host is offering in this listing
  - available_spots     : how many are still open (â‰¤ total_spots)
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Text
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

    # Listing type (e.g. "Room for Rent", "Self-contained", "Bedspace"). Nullable
    # so existing rows are valid; populated by the create/edit forms going forward.
    listing_type = Column(String, nullable=True)

    # Coordinates for the geo-intelligence map. Nullable until geocoded/entered.
    latitude    = Column(Float, nullable=True)
    longitude   = Column(Float, nullable=True)

    # Timestamps
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # FK to owner (landlord or student_host)
    owner_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner       = relationship("User", back_populates="listings")

    # â”€â”€ Student Host bedspace fields â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Which institution the bedspace is near (e.g. "UNZA", "CBU")
    nearest_institution = Column(String, nullable=True, index=True)

    # Availability toggle â€” host can mark a listing as taken without deleting
    # This is separate from admin "status" (pending/active/rejected).
    # "available" means spots are open; "taken" means fully occupied.
    availability_status = Column(String, default="available", nullable=False)

    # Spot management â€” how many bedspaces in this listing
    total_spots     = Column(Integer, default=1, nullable=False)

    # Student facing property attributes (all optional)
    bedrooms            = Column(Integer, nullable=True)
    bathrooms           = Column(Integer, nullable=True)
    furnished           = Column(String, nullable=True)   # yes, semi, no
    water_supply        = Column(String, nullable=True)   # yes, borehole, mains, no
    electricity         = Column(String, nullable=True)   # prepaid, postpaid, solar, none
    parking             = Column(String, nullable=True)   # yes, no
    curfew              = Column(String, nullable=True)   # none, 22:00, 23:00, 00:00
    gender_preference   = Column(String, nullable=True)   # mixed, female, male
    distance_to_campus  = Column(String, nullable=True)   # free text, e.g. 1.2 km
    amenities           = Column(Text, nullable=True)     # JSON list of strings
    available_spots = Column(Integer, default=1, nullable=False)

    # â”€â”€ Multi-media (NEW) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
