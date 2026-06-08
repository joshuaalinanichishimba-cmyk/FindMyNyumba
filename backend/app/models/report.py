"""
app/models/report.py
Report model — students flag suspicious or misleading listings or users.

Workflow status values: open | investigating | reviewed | resolved | dismissed
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = {'extend_existing': True}

    id          = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"), nullable=True, index=True)
    reported_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    reason      = Column(String, nullable=False)   # e.g. "scam", "misleading", "harassment"
    description = Column(Text, nullable=True)

    # Workflow: open | investigating | reviewed | resolved | dismissed
    status      = Column(String, default="open", index=True)

    admin_note  = Column(Text, nullable=True)

    # Set when an admin moves the report along
    resolution  = Column(Text, nullable=True)       # what the admin did / decided
    handled_by  = Column(Integer, ForeignKey("users.id"), nullable=True)
    handled_at  = Column(DateTime(timezone=True), nullable=True)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    reporter      = relationship("User", foreign_keys=[reporter_id])
    listing       = relationship("Listing", foreign_keys=[listing_id])
    reported_user = relationship("User", foreign_keys=[reported_user_id])
    handler       = relationship("User", foreign_keys=[handled_by])
