from fastapi import APIRouter
from app.api.v1.endpoints import auth, properties, reviews, admin

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Security & Auth"])
api_router.include_router(properties.router, prefix="/properties", tags=["Property Management"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["Public Feedback"])
api_router.include_router(admin.router, prefix="/admin", tags=["System Administration"])
