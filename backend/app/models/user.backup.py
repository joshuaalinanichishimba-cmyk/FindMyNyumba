from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="student")
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Profile
    phone_number = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    
    # Landlord Specific Fields
    business_name = Column(String, nullable=True)
    business_location = Column(String, nullable=True)
    id_number = Column(String, nullable=True)
    
    # Notification Preferences
    email_alerts = Column(Boolean, default=True)
    sms_alerts = Column(Boolean, default=False)
    
    # Verification Workflow
    verification_status = Column(String, default="unverified")
    verification_rejection_reason = Column(String, nullable=True)