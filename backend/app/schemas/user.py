from pydantic import BaseModel, EmailStr, field_validator
from app.core.security import validate_password_strength
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    phone_number: Optional[str] = None
    business_name: Optional[str] = None
    business_location: Optional[str] = None

class UserCreate(UserBase):
    password: str
    id_number: Optional[str] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: Optional[bool] = False
    verification_status: Optional[str] = "unverified"
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
