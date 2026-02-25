from fastapi import APIRouter
from app.api.v1 import auth, messages, properties, reviews, admin

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
