from fastapi import APIRouter, Depends
from app.api.v1.auth import get_current_user

router = APIRouter()

@router.get("/stats")
async def get_system_stats(current_user=Depends(get_current_user)):
    # Fixed the dictionary syntax by making everything key-value pairs
    return {
        "listings_count": 0, 
        "users_count": 0, 
        "user_role": current_user.role
    }
