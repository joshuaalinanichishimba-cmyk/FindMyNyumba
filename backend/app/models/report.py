"""
app/models/report.py
Report model — students/users can flag suspicious listings or users.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)

    # Who filed the report
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # What is being reported (listing or user — only one will be set)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=True, index=True)
    reported_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Report details
    reason = Column(String, nullable=False)       # e.g. "scam", "misleading", "harassment"
    description = Column(Text, nullable=True)

    # Admin workflow
    status = Column(String, default="open")       # open | reviewed | dismissed
    admin_note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
