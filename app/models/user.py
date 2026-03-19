from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String) # student or landlord
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Profile & Settings Fields
    phone_number = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    email_alerts = Column(Boolean, default=True)
    sms_alerts = Column(Boolean, default=False)

    # --- THE MISSING LINK ---
    # This connects the User to their Listings (for Landlords)
    listings = relationship("Listing", back_populates="owner")