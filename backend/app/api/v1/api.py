"""
app/api/v1/api.py
"""
from fastapi import APIRouter

from app.api.v1.endpoints.auth          import router as auth_router
from app.api.v1.endpoints.users         import router as users_router
from app.api.v1.endpoints.listings      import router as listings_router
from app.api.v1.endpoints.students      import router as students_router
from app.api.v1.endpoints.messages      import router as messages_router
from app.api.v1.endpoints.landlords     import router as landlords_router
from app.api.v1.endpoints.student_hosts import router as student_hosts_router
from app.api.v1.endpoints.admin         import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router,          prefix="/auth")
api_router.include_router(users_router,         prefix="/users")
api_router.include_router(listings_router)
api_router.include_router(students_router)
api_router.include_router(messages_router)
api_router.include_router(landlords_router)
api_router.include_router(student_hosts_router)
api_router.include_router(admin_router)