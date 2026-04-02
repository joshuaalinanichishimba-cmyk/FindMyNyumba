"""
app/models/report.py
Report model — students flag suspicious or misleading listings.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = {'extend_existing': True}

    id          = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    listing_id  = Column(Integer, ForeignKey("listings.id"), nullable=True, index=True)

    reason      = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Workflow: pending | reviewed | dismissed
    status     = Column(String, default="pending", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id])
    listing  = relationship("Listing", foreign_keys=[listing_id])
