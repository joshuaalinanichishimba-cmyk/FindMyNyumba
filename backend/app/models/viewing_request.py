"""
app/models/viewing_request.py

A student's request to physically view a listing before committing — the
"spine" of the marketplace. Purely additive: this is a brand-new table that
does not touch any existing data.

landlord_id is denormalised onto the row (copied from the listing's owner at
creation time) so the landlord's "incoming requests" query is a simple indexed
lookup instead of a join through listings on every dashboard load.

Status lifecycle (validated in the endpoint, stored as a plain string to stay
portable across SQLite dev and Postgres prod):
    pending   -> student submitted, awaiting landlord
    confirmed -> landlord accepted the date/time
    declined  -> landlord declined
    completed -> the viewing happened
    cancelled -> student withdrew the request
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ViewingRequest(Base):
    __tablename__ = "viewing_requests"
    __table_args__ = {"extend_existing": True}

    id          = Column(Integer, primary_key=True, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    student_id  = Column(Integer, ForeignKey("users.id"),    nullable=False, index=True)
    landlord_id = Column(Integer, ForeignKey("users.id"),    nullable=False, index=True)

    preferred_date = Column(String, nullable=False)   # "YYYY-MM-DD" from the date input
    preferred_time = Column(String, nullable=False)   # "HH:MM" from the time input
    notes          = Column(Text,   nullable=True)

    status     = Column(String, nullable=False, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    listing  = relationship("Listing",  foreign_keys=[listing_id])
    student  = relationship("User",     foreign_keys=[student_id])
    landlord = relationship("User",     foreign_keys=[landlord_id])
