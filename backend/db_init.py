import sys
import os
sys.path.append(os.getcwd())
from app.db.session import engine

# Import BOTH models so SQLAlchemy sees them
from app.models.user import User
from app.models.property import Property

# Import the Base they both use
try:
    from app.db.base import Base
except ImportError:
    from app.db.session import Base

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("SUCCESS: Database tables (users, properties) created!")
