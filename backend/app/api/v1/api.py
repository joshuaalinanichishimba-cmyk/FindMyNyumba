from fastapi import APIRouter
from app.api.v1.endpoints import auth, listings, messages, students, landlords, student_hosts, admin

api_router = APIRouter()

api_router.include_router(auth.router,          prefix="/auth",         tags=["Auth"])
api_router.include_router(listings.router,      prefix="",              tags=["Properties"])
api_router.include_router(messages.router,      prefix="",              tags=["Messages"])
api_router.include_router(students.router,      prefix="",              tags=["Students"])
api_router.include_router(landlords.router,     prefix="",              tags=["Landlord"])
api_router.include_router(student_hosts.router, prefix="",              tags=["Student Host"])
api_router.include_router(admin.router,         prefix="",              tags=["Admin"])