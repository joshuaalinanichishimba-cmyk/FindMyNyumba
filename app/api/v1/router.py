from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, listings, uploads

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/login", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(listings.router, prefix="/listings", tags=["listings"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
