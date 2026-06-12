"""
app/core/database.py
Creates the SQLAlchemy engine from settings.DATABASE_URL.
Handles both PostgreSQL (production / Supabase) and SQLite (local) automatically.

WHAT CHANGED vs the previous version
------------------------------------
1. pool_pre_ping=True
   Supabase / PgBouncer silently drop idle connections. Without pre-ping,
   SQLAlchemy hands the next request a dead connection and you get random
   "server closed the connection unexpectedly" 500s minutes after low traffic.
   pre_ping issues a cheap liveness check and transparently reconnects.

2. pool_recycle=300
   Proactively recycle connections older than 5 minutes, so they never go
   stale enough for a managed Postgres to have closed them server-side.

3. Bounded pool (pool_size / max_overflow)
   Prevents a traffic burst from exhausting Supabase's connection limit.
   Tune to your plan; these are conservative, safe defaults.

4. declarative_base imported from sqlalchemy.orm (the SQLAlchemy 2.0 location)
   instead of the deprecated sqlalchemy.ext.declarative path.

These changes are backwards-compatible: no model, query, or session-usage
changes are required anywhere else.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

if DATABASE_URL.startswith("sqlite"):
    # SQLite (local dev/tests): single-file DB, allow cross-thread use.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    # PostgreSQL (production / Supabase).
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,     # verify/reconnect dead connections before use
        pool_recycle=300,       # recycle connections older than 5 min
        pool_size=5,            # steady-state connections kept open
        max_overflow=10,        # extra connections allowed under burst
        pool_timeout=30,        # seconds to wait for a free connection
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session per request.
    Always closes the session when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
