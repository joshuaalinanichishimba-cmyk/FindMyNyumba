"""
main.py — FindMyNyumba FastAPI entry point

FIXES:
- Correct import paths for all endpoint modules
- All routers registered (auth, student, landlord, student_host, admin, listings, messages)
- CORS: allow_credentials=True is incompatible with allow_origins=["*"]
  Replaced with explicit origins from settings; falls back to localhost for dev
- Removed the inline /api/v1/properties stub that always returned []
  (the real listings router handles this now with DB-backed data + filters)
- Static file serving added so uploaded images are reachable
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.v1.endpoints import auth, student, landlords, student_hosts, admin, listings, messages

app = FastAPI(title="FindMyNyumba", version="1.0.0")

# -- CORS ----------------------------------------------------------------------
# allow_credentials=True cannot be combined with allow_origins=["*"].
# Use explicit origins in production; keep dev origins for local testing.
ALLOWED_origins = ["https://find-my-nyumba-original.vercel.app", "https://nyumba-web.vercel.app", 
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Add your production frontend URL here, e.g.:
    # "https://findmynyumba.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Static files (uploaded property images, attachments, verification docs) ---
# Creates the directory if absent so the app doesn't crash on a fresh clone.
for static_dir in ["static/uploads/properties", "static/uploads/attachments", "static/uploads/verification"]:
    Path(static_dir).mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# -- Health check --------------------------------------------------------------
@app.get("/")
def home():
    return {"status": "online", "project": "FindMyNyumba"}

# -- Routers -------------------------------------------------------------------
# Auth  (login, register, forgot-password, /me)
app.include_router(auth.router,          prefix="/api/v1/auth")

# Public property listings  (browse, detail, reviews, reports)
app.include_router(listings.router,      prefix="/api/v1")

# Messages  (send, conversations, thread, unread-count)
app.include_router(messages.router,      prefix="/api/v1")

# Student dashboard  (overview, profile, saved, password)
app.include_router(student.router,       prefix="/api/v1")

# Landlord dashboard  (properties CRUD, inquiries, verification, profile)
app.include_router(landlords.router,     prefix="/api/v1")

# Student Host dashboard  (listings CRUD, verification, profile)
app.include_router(student_hosts.router, prefix="/api/v1")

# Admin panel  (users, listings, verifications, reports, analytics, settings)
app.include_router(admin.router,         prefix="/api/v1")
