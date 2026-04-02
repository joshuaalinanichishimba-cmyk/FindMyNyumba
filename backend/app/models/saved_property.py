"""
app/models/saved_property.py

Junction table: one row per (user, listing) pair a student has saved.
Uses property_id (not listing_id) to match the query in student_endpoints.py.
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from datetime import datetime
from app.core.database import Base

class SavedProperty(Base):
    __tablename__ = "saved_properties"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Named property_id to match how student_endpoints.py queries it
    property_id = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)