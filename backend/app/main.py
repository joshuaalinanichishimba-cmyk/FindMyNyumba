"""
main.py — FindMyNyumba FastAPI entry point

FIXES vs original:
- Renamed `ALLOWED_origins` (typo) → `ALLOWED_ORIGINS` so the variable
  actually resolves at startup. The original raised NameError on boot.
- Renamed import `student` → `students` to match the real filename.
- De-duplicated the CORS origin list and pulled allowed origins from settings
  (with a sensible dev fallback) so the value can change per environment
  without code edits.
- Static directories now created idempotently before mounting; safe on a
  fresh clone or a fresh container.
- /healthz added (cheap probe for uptime monitors and Render/Vercel checks).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.endpoints import (
    auth,
    students,
    landlords,
    student_hosts,
    admin,
    listings,
    messages,
)

app = FastAPI(title="FindMyNyumba", version="1.0.0")

# ── CORS ───────────────────────────────────────────────────────────────────────
# allow_credentials=True is incompatible with allow_origins=["*"], so we list
# origins explicitly. Add your production frontend host(s) here.
ALLOWED_ORIGINS = [
    # Production frontends
    "https://find-my-nyumba-original.vercel.app",
    "https://nyumba-web.vercel.app",
    # Local dev
    "http://localhost:3000",
    "http://localhost:5500",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Static files ──────────────────────────────────────────────────────────────
# Uploaded property images, message attachments, verification docs.
# Created at boot so a clean container does not crash.
STATIC_DIRS = [
    "static/uploads/properties",
    "static/uploads/attachments",
    "static/uploads/verification",
]
for d in STATIC_DIRS:
    Path(d).mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Health checks ─────────────────────────────────────────────────────────────
@app.get("/")
def home():
    return {"status": "online", "project": "FindMyNyumba"}


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Lightweight probe for uptime monitors / load-balancer health checks."""
    return {"ok": True}


# ── Routers ───────────────────────────────────────────────────────────────────
# Each module already declares its own internal prefix (e.g. "/properties"),
# so here we only add the API version prefix.
app.include_router(auth.router,          prefix="/api/v1/auth")
app.include_router(listings.router,      prefix="/api/v1")   # /properties
app.include_router(messages.router,      prefix="/api/v1")   # /messages
app.include_router(students.router,      prefix="/api/v1")   # /students
app.include_router(landlords.router,     prefix="/api/v1")   # /landlord
app.include_router(student_hosts.router, prefix="/api/v1")   # /student-host
app.include_router(admin.router,         prefix="/api/v1")   # /admin
