"""
main.py
FindMyNyumba FastAPI application entry point.

IMPORTANT:
- landlords.py and student_hosts.py routers have prefix="/landlord" and
  "/student-host" respectively (NOT "/api/v1/..."). The "/api/v1" prefix
  is added here via api_router mounted at prefix="/api/v1".
- CORS is restricted to known origins. Do NOT use allow_origins=["*"] with
  allow_credentials=True — that violates the CORS spec and is a security risk.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import Base, engine

# Import all models so SQLAlchemy registers them before create_all
import app.models  # noqa: F401

# ── Create DB tables on startup (idempotent) ──────────────────────────────────
# In production you would use Alembic migrations instead.
Base.metadata.create_all(bind=engine)

# ── Ensure static upload directory exists ────────────────────────────────────
os.makedirs("static/uploads/properties",    exist_ok=True)
os.makedirs("static/uploads/verification",  exist_ok=True)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    # Hide /docs and /redoc in production — set to None when deploying
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_credentials=True requires explicit origins — never use ["*"] with it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── Static files (uploaded property images, verification docs) ───────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── API routes ────────────────────────────────────────────────────────────────
# All sub-routers are registered inside api_router (see app/api/v1/api.py).
# The "/api/v1" prefix is added once here.
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "api": "/api/v1",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}

from fastapi.responses import FileResponse
import pathlib

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    # Serve favicon from the static folder if it exists, otherwise return 204 No Content
    favicon_path = pathlib.Path("static/favicon.ico")
    if favicon_path.exists():
        return FileResponse(str(favicon_path))
    from fastapi.responses import Response
    return Response(status_code=204)
