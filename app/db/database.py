from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base # ADDED
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 1. Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=getattr(settings, 'DEBUG', False),  
    pool_pre_ping=True    
)

# 2. Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 3. Create the Base class - THIS WAS THE MISSING LINK
# All your models (User, Role) must inherit from this Base
Base = declarative_base()

def get_db():
    """
    Dependency for getting database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() # Removed the period/error from your snippet