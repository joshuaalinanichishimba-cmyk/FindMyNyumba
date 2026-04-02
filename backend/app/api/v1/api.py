from fastapi import APIRouter
from app.api.v1.endpoints import (
    properties, users, auth, landlords,
    messages, students, student_hosts, admin
)

api_router = APIRouter()

# Core & Public
# NOTE: prefixes are defined inside each router file — do NOT add them here too.
api_router.include_router(auth.router)
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(properties.router)
api_router.include_router(messages.router)

# Dashboards
api_router.include_router(students.router)
api_router.include_router(student_hosts.router)
api_router.include_router(landlords.router)
api_router.include_router(admin.router)
