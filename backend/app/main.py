"""
main.py
FindMyNyumba FastAPI application entry point.

WHAT CHANGED IN THIS VERSION
----------------------------
1. Sentry is now actually initialised (it was in requirements.txt but unused),
   so unhandled errors are captured off-box. Render's disk is ephemeral, so a
   local error.log is wiped on every deploy — Sentry fixes that. It only turns
   on when SENTRY_DSN is set, so local dev is unaffected.
2. Rate limiting is wired in via setup_rate_limiting(app). The limiter existed
   but was never attached, so /auth/login had no brute-force protection.
3. A small SecurityHeadersMiddleware adds HSTS / X-Content-Type-Options /
   X-Frame-Options / Referrer-Policy to every response.
4. The mojibake comment blocks from the previous file were removed; logic is
   unchanged.

IMPORTANT (unchanged behaviour):
- Sub-routers are registered inside api_router (see app/api/v1/api.py); the
  "/api/v1" prefix is added once here.
- CORS is restricted to known origins. Never use allow_origins=["*"] together
  with allow_credentials=True.
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.rate_limiter import setup_rate_limiting
from app.models.viewing_request import ViewingRequest   # noqa: F401

# --- Optional Sentry error monitoring -------------------------------------
# Only initialises if SENTRY_DSN is present in the environment, so local dev
# and tests stay quiet. Add SENTRY_DSN to Render's env vars to switch it on.
_SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
if _SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            # Keep tracing light/free-tier friendly; raise later if you want APM.
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            send_default_pii=False,
            environment=os.getenv("SENTRY_ENV", "production" if settings.PRODUCTION else "development"),
        )
    except Exception as exc:  # never let monitoring setup break startup
        print(f"[startup] Sentry init skipped: {exc}")

# --- Import ALL models before create_all so every table is registered -----
from app.models.user import User                       # noqa: E402,F401
from app.models.password_reset import PasswordResetToken  # noqa: E402,F401
from app.models.listing import Listing                 # noqa: E402,F401
from app.models.saved_listing import SavedListing      # noqa: E402,F401
from app.models.report import Report                   # noqa: E402,F401
from app.models.admin_models import (                  # noqa: E402,F401
    Transaction, Escrow, Institution, Notification,
    AuditLog, AdminNote, RolePermission,
)
from app.models.listing_event import ListingEvent      # noqa: E402,F401
from app.models.review import Review                 # noqa: E402,F401

# --- Create any missing tables (idempotent; safe on every startup) --------
Base.metadata.create_all(bind=engine)

# One-time: add report-workflow / verification columns if missing.
from sqlalchemy import text as _sql_text  # noqa: E402

with engine.connect() as _conn:
    for _ddl in [
        "ALTER TABLE users ADD COLUMN verification_doc1_url VARCHAR",
        "ALTER TABLE users ADD COLUMN verification_doc2_url VARCHAR",
        "ALTER TABLE reports ADD COLUMN reported_user_id INTEGER",
        "ALTER TABLE reports ADD COLUMN admin_note TEXT",
        "ALTER TABLE reports ADD COLUMN resolution TEXT",
        "ALTER TABLE reports ADD COLUMN handled_by INTEGER",
        "ALTER TABLE reports ADD COLUMN handled_at TIMESTAMP",
    ]:
        try:
            _conn.execute(_sql_text(_ddl))
            _conn.commit()
        except Exception:
            pass  # column already exists


def _ensure_columns():
    """create_all() only CREATES missing tables; it never ALTERs existing ones.
    The Listing table predates listing_type/latitude/longitude, so add them.
    Postgres supports IF NOT EXISTS; SQLite doesn't, so catch the dup-column error."""
    from sqlalchemy import text
    cols = {"listing_type": "VARCHAR", "latitude": "FLOAT", "longitude": "FLOAT"}
    is_pg = engine.dialect.name == "postgresql"
    try:
        with engine.begin() as conn:
            for col, typ in cols.items():
                if is_pg:
                    conn.execute(text(f"ALTER TABLE listings ADD COLUMN IF NOT EXISTS {col} {typ}"))
                else:
                    try:
                        conn.execute(text(f"ALTER TABLE listings ADD COLUMN {col} {typ}"))
                    except Exception:
                        pass
    except Exception as e:  # never block startup on a migration hiccup
        print(f"[startup] column ensure skipped: {e}")


_ensure_columns()

# --- Ensure static upload directories exist -------------------------------
os.makedirs("static/uploads/properties",   exist_ok=True)
os.makedirs("static/uploads/verification", exist_ok=True)


# --- Security headers middleware ------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds baseline security headers to every response. Cheap, no deps."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # HSTS only matters over HTTPS; harmless to send and ignored on http.
        if settings.PRODUCTION:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


# --- App ------------------------------------------------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    # Consider setting docs_url=None / redoc_url=None in production.
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting: attach the shared limiter + 429 handler.
setup_rate_limiting(app)

# Security headers on every response.
app.add_middleware(SecurityHeadersMiddleware)

# CORS — allow_credentials=True requires explicit origins; never use ["*"].
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Static files (uploaded property images, verification docs).
app.mount("/static", StaticFiles(directory="static"), name="static")

# API routes — "/api/v1" prefix added once here.
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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    import pathlib
    favicon_path = pathlib.Path("static/favicon.ico")
    if favicon_path.exists():
        return FileResponse(str(favicon_path))
    return Response(status_code=204)
