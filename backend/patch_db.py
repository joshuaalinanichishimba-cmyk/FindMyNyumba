import sys
import os

# Ensure Python can find the 'app' module
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.core.database import engine

try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0 NOT NULL;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS lockout_until TIMESTAMP WITH TIME ZONE;"))
    print("✅ Database successfully patched with new security columns!")
except Exception as e:
    print(f"❌ Error: {e}")
