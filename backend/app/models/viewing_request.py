"""
app/models/viewing_request.py

A student's request to physically view a listing before committing -- the
"spine" of the marketplace.

WHAT CHANGED IN THIS VERSION
----------------------------
1. Added the full response lifecycle the landlord/host needs:
     - landlord_notes    : free-text note the landlord attaches on respond/reschedule
     - rescheduled_date  : landlord-proposed new date ("YYYY-MM-DD")
     - rescheduled_time  : landlord-proposed new time ("HH:MM")
2. Introduced a ViewingStatus enum so the allowed states are defined in one
   place and shared by the endpoints. Values are stored as lowercase strings
   (portable across SQLite dev and Postgres prod, and compatible with rows that
   already have status="pending").

NOTE ON NAMING
--------------
The platform's property table is `listings` (model `Listing`), so the foreign
key here stays `listing_id`. The viewing-request API also accepts/returns
`property_id` as an alias for callers that use that word -- it is the same value.

landlord_id is denormalised onto the row (copied from the listing's owner at
creation time) so the landlord's "incoming requests" query is a simple indexed
lookup instead of a join through listings on every dashboard load.

Status lifecycle (validated in the endpoint):
    pending     -> student submitted, awaiting landlord
    accepted    -> landlord accepted the date/time
    rescheduled -> landlord proposed a new date/time, awaiting student
    rejected    -> landlord declined
    cancelled   -> student withdrew the request
    expired     -> the preferred date/time passed while still pending

MIGRATION (existing table already created by create_all):
    create_all() never ALTERs an existing table, so the three new columns must
    be added once at startup. See the snippet to drop into main.py's startup
    DDL loop (provided with this change).
"""
import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ViewingStatus(str, enum.Enum):
    """Canonical viewing-request states. `str` mixin so the members compare and
    serialise as their plain lowercase value (e.g. ViewingStatus.PENDING == 'pending')."""
    PENDING     = "pending"
    ACCEPTED    = "accepted"
    RESCHEDULED = "rescheduled"
    REJECTED    = "rejected"
    CANCELLED   = "cancelled"
    EXPIRED     = "expired"
    COMPLETED   = "completed"
    MISSED      = "missed"


class ViewingRequest(Base):
    __tablename__ = "viewing_requests"
    __table_args__ = {"extend_existing": True}

    id          = Column(Integer, primary_key=True, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    student_id  = Column(Integer, ForeignKey("users.id"),    nullable=False, index=True)
    landlord_id = Column(Integer, ForeignKey("users.id"),    nullable=False, index=True)

    # Student's requested slot.
    preferred_date = Column(String, nullable=False)   # "YYYY-MM-DD"
    preferred_time = Column(String, nullable=False)   # "HH:MM"
    notes          = Column(Text,   nullable=True)    # student's message to the landlord

    # Landlord response fields (new).
    landlord_notes   = Column(Text,   nullable=True)  # landlord's note on accept/reject/reschedule
    rescheduled_date = Column(String, nullable=True)  # landlord-proposed new date
    rescheduled_time = Column(String, nullable=True)  # landlord-proposed new time

    status     = Column(String, nullable=False, default=ViewingStatus.PENDING.value, index=True)

    # Viewing code + completion tracking (Feature 5). Code is generated when the
    # landlord ACCEPTS, shown to the student, and verified by the landlord at the
    # physical viewing to mark it completed (the trust signal that gates reviews).
    viewing_code  = Column(String, nullable=True, unique=True, index=True)  # "FMN-XXXXXX"
    code_verified = Column(Boolean, nullable=False, server_default="false", default=False)
    completed_at  = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    listing  = relationship("Listing", foreign_keys=[listing_id])
    student  = relationship("User",    foreign_keys=[student_id])
    landlord = relationship("User",    foreign_keys=[landlord_id])
