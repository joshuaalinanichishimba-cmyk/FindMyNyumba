from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from datetime import datetime
from app.core.database import Base

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"))
    target_id = Column(Integer, nullable=True) # Can be a listing ID or Landlord ID
    reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)