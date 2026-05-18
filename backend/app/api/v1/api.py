"""
app/api/v1/api.py

Central router aggregator.  Every endpoint module is registered here once.
main.py mounts this under /api/v1, so the final paths are:

  /api/v1/auth/*           ← auth.py
  /api/v1/properties/*     ← listings.py
  /api/v1/students/*       ← students.py
  /api/v1/messages/*       ← messages.py
  /api/v1/landlord/*       ← landlords.py
  /api/v1/student-host/*   ← student_hosts.py
  /api/v1/admin/*          ← admin.py
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth          import router as auth_router
from app.api.v1.endpoints.listings      import router as listings_router
from app.api.v1.endpoints.students      import router as students_router
from app.api.v1.endpoints.messages      import router as messages_router
from app.api.v1.endpoints.landlords     import router as landlords_router
from app.api.v1.endpoints.student_hosts import router as student_hosts_router
from app.api.v1.endpoints.admin         import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router,          prefix="/auth")
api_router.include_router(listings_router)       # already has prefix="/properties"
api_router.include_router(students_router)       # already has prefix="/students"
api_router.include_router(messages_router)       # already has prefix="/messages"
api_router.include_router(landlords_router)      # already has prefix="/landlord"
api_router.include_router(student_hosts_router)  # already has prefix="/student-host"
api_router.include_router(admin_router)          # already has prefix="/admin"
