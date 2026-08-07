"""
app/models/assistant_profile.py
Reputation and public-profile data for Accommodation Assistants.
One row per assistant (FK to users). Keeps assistant-specific fields off the
lean users table and groups everything the profile page and search rely on.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, JSON
from app.core.database import Base


class AssistantProfile(Base):
    __tablename__ = "assistant_profiles"

    id                    = Column(Integer, primary_key=True, index=True)
    user_id               = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # public profile
    bio                   = Column(Text, nullable=True)
    areas_covered         = Column(JSON, nullable=True)   # e.g. ["Riverside", "Kansenshi"]
    languages             = Column(JSON, nullable=True)   # e.g. ["English", "Bemba"]
    current_status        = Column(String, default="available", nullable=False)  # available | busy | offline

    # reputation
    trust_score           = Column(Integer, default=0, nullable=False)   # 0-100
    rating                = Column(Numeric, default=0, nullable=False)   # avg star rating
    rating_count          = Column(Integer, default=0, nullable=False)
    successful_placements = Column(Integer, default=0, nullable=False)
    cancelled_placements  = Column(Integer, default=0, nullable=False)
    response_rate         = Column(Numeric, default=0, nullable=False)   # 0-100 (%)
    avg_response_seconds  = Column(Integer, nullable=True)
    years_active          = Column(Numeric, default=0, nullable=False)
    profile_completeness  = Column(Integer, default=0, nullable=False)   # 0-100 (%)

    created_at            = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
