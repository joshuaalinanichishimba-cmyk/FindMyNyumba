from pydantic import BaseModel, EmailStr
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
    is_verified: bool
    verification_status: str
    avatar_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True