from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str

class PropertyCreate(BaseModel):
    title: str
    description: str
    price: float
    location: str
    photo_url: Optional[str] = None
    landlord_id: int

    # Shared Housing Fields
    number_of_current_occupants: Optional[int] = None
    total_capacity: Optional[int] = None
    gender_preference: Optional[str] = None
    rent_split_amount: Optional[float] = None
    utilities_included: Optional[bool] = None
    furnished: Optional[bool] = None
    move_in_date: Optional[str] = None
    house_rules: Optional[str] = None
    quiet_study_environment: Optional[bool] = None
    visitor_policy: Optional[str] = None

class PropertyResponse(PropertyCreate):
    id: int
    # Shared Housing Fields
    number_of_current_occupants: Optional[int] = None
    total_capacity: Optional[int] = None
    gender_preference: Optional[str] = None
    rent_split_amount: Optional[float] = None
    utilities_included: Optional[bool] = None
    furnished: Optional[bool] = None
    move_in_date: Optional[str] = None
    house_rules: Optional[str] = None
    quiet_study_environment: Optional[bool] = None
    visitor_policy: Optional[str] = None

    class Config:
        from_attributes = True




# --- Authentication Schemas ---
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordSubmit(BaseModel):
    token: str
    new_password: str
