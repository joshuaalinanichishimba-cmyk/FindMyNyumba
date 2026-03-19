import sys
import os

# Add the current directory to path so we can import 'app'
sys.path.append(os.getcwd())

from app.core.database import engine, Base
# EXPLICITLY IMPORT ALL MODELS SO SQLALCHEMY SEES THEM
from app.models.user import User
from app.models.listing import Listing
from app.models.property import Property
from app.models.role import Role
from app.models.saved_property import SavedProperty
from app.models.message import Message
from app.models.report import Report

def init_db():
    print("🚀 Initializing Database...")
    try:
        # This command creates all tables that don't exist yet
        Base.metadata.create_all(bind=engine)
        print("✅ SUCCESS: All tables (users, listings, messages, etc.) have been created!")
    except Exception as e:
        print(f"❌ ERROR: Could not initialize database: {e}")

if __name__ == "__main__":
    init_db()