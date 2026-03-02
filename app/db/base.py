# app/db/base.py

# 1. Import the Base from the source of truth (database.py)
from app.db.database import Base 

# 2. Import all models here so Alembic can see them
# Note: Ensure your models (user.py) import Base from app.db.database, NOT here.
from app.models.user import User
from app.models.role import Role

# 3. Explicitly link the metadata
metadata = Base.metadata
