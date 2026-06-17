"""
app/api/v1/api.py
Master API router.
This is the ONLY place sub-routers are registered.
main.py mounts this with prefix="/api/v1", so each sub-router here
must NOT include "/api/v1" in its own prefix.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, admin, listings, messages, landlords, student_hosts, students, notifications
from app.api.v1.endpoints import trust, verification, fraud, admin_trust, admin_extra

api_router = APIRouter()

# â”€â”€ Public / Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
api_router.include_router(auth.router)         # /api/v1/auth/...
api_router.include_router(listings.router)     # /api/v1/properties/...
api_router.include_router(messages.router)     # /api/v1/messages/...

# â”€â”€ Role dashboards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
api_router.include_router(landlords.router)    # /api/v1/landlord/...
api_router.include_router(student_hosts.router)# /api/v1/student-host/...
api_router.include_router(students.router)     # /api/v1/students/...

# â”€â”€ Admin â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
api_router.include_router(admin.router)        # /api/v1/admin/...
api_router.include_router(admin_extra.router)  # /api/v1/admin/... (extended)
api_router.include_router(notifications.router) # /api/v1/notifications/...

# -- Trust & Safety --
api_router.include_router(trust.router)
api_router.include_router(verification.router)
api_router.include_router(fraud.router)
api_router.include_router(admin_trust.router)
