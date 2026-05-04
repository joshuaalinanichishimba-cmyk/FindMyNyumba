from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

api_router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@api_router.post("/auth/login")
async def login(request: LoginRequest):
    # Simple test login - accepts any credentials for testing
    return {
        "access_token": "test_token_12345",
        "token_type": "bearer",
        "role": "student",
        "user_id": 1,
        "full_name": "Test User"
    }

@api_router.post("/auth/register")
async def register():
    return {"message": "Registration endpoint", "user_id": 1}

@api_router.get("/auth/me")
async def get_current_user():
    return {
        "id": 1,
        "full_name": "Test User",
        "email": "test@example.com",
        "role": "student",
        "is_active": True
    }

@api_router.get("/students/dashboard/overview")
async def student_overview():
    return {
        "stats": {
            "saved_count": 5,
            "unread_messages_count": 2
        },
        "recent_properties": [
            {
                "id": 1,
                "title": "Cozy Studio Near Campus",
                "price": 2500,
                "location": "Lusaka",
                "image_url": None,
                "is_boosted": False
            }
        ]
    }

@api_router.get("/properties")
async def get_properties():
    return [
        {
            "id": 1,
            "title": "Cozy Studio Near Campus",
            "price": 2500,
            "location": "Lusaka",
            "image_url": None,
            "is_boosted": False
        },
        {
            "id": 2,
            "title": "Spacious 2-Bedroom Apartment",
            "price": 4500,
            "location": "Lusaka",
            "image_url": None,
            "is_boosted": True
        }
    ]

@api_router.get("/properties/{listing_id}")
async def get_property(listing_id: int):
    return {
        "id": listing_id,
        "title": "Test Property",
        "price": 2500,
        "location": "Lusaka",
        "description": "A beautiful property near the university.",
        "image_url": None,
        "is_boosted": False,
        "owner_id": 1,
        "owner": {
            "id": 1,
            "full_name": "John Doe",
            "role": "landlord",
            "verification_status": "verified"
        }
    }
