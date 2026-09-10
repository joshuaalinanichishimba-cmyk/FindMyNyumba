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

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: Optional[bool] = False
    verification_status: Optional[str] = "unverified"
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    institution: Optional[str] = None
    student_id_number: Optional[str] = None
    preferred_zone: Optional[str] = None
    room_type: Optional[str] = None
    max_rent: Optional[int] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    whatsapp_alerts: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    hide_phone: Optional[bool] = None
    email_alerts: Optional[bool] = None

    class Config:
        from_attributes = True