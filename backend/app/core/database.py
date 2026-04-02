"""
app/core/database.py

Creates the SQLAlchemy engine from settings.DATABASE_URL.
Handles both PostgreSQL and SQLite automatically.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

# SQLite needs check_same_thread=False; PostgreSQL does not accept it
# We detect which DB is in use and set connect_args accordingly
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL (or any other DB)
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
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