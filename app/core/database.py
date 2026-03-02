from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 1. Create the Engine
# 'check_same_thread' is only needed for SQLite
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# 2. Create a Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Create the Base class for models
Base = declarative_base()

# 4. The missing piece: The get_db dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
