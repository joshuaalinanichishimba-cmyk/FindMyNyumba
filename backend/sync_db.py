import sys
import os
sys.path.append(os.getcwd())
from app.core.database import engine, Base
from app.models.user import User
from app.models.property import Property

def init_db():
    print("🚀 Initializing FindMyNyumba Database...")
    try:
        # This will create the tables in the database you saw in your \l list
        Base.metadata.create_all(bind=engine)
        print("✅ Success! Tables created correctly.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    init_db()
