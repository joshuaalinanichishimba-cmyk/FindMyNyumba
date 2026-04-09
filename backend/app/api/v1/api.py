"""
app/api/v1/api.py

Central router that registers all endpoint sub-routers.
Mounted at /api/v1 in main.py.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth          import router as auth_router
from app.api.v1.endpoints.admin         import router as admin_router
from app.api.v1.endpoints.landlords     import router as landlord_router
from app.api.v1.endpoints.student_hosts import router as student_host_router
from app.api.v1.endpoints.students      import router as student_router
from app.api.v1.endpoints.messages      import router as messages_router
from app.api.v1.endpoints.properties    import router as properties_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(landlord_router)
api_router.include_router(student_host_router)
api_router.include_router(student_router)
api_router.include_router(messages_router)
api_router.include_router(properties_router)
