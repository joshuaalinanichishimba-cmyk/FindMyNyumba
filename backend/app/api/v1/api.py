"""
app/api/v1/api.py
Master API router.
This is the ONLY place sub-routers are registered.
main.py mounts this with prefix="/api/v1", so each sub-router here
must NOT include "/api/v1" in its own prefix.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, admin, listings, messages, landlords, student_hosts, students

api_router = APIRouter()

# ── Public / Auth ─────────────────────────────────────────────────────────────
api_router.include_router(auth.router)         # /api/v1/auth/...
api_router.include_router(listings.router)     # /api/v1/properties/...
api_router.include_router(messages.router)     # /api/v1/messages/...

# ── Role dashboards ───────────────────────────────────────────────────────────
api_router.include_router(landlords.router)    # /api/v1/landlord/...
api_router.include_router(student_hosts.router)# /api/v1/student-host/...
api_router.include_router(students.router)     # /api/v1/students/...

# ── Admin ─────────────────────────────────────────────────────────────────────
api_router.include_router(admin.router)        # /api/v1/admin/...
