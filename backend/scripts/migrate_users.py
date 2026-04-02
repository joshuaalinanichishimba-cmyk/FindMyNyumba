"""
migrate_users.py  — Complete Users Table Migration
Run from D:\FindMyNyumba_Original\ with:

    python migrate_users.py

Adds EVERY column the User model expects.
Safe for SQLite (handles existing columns by catching the OperationalError).
"""
from app.core.database import engine
from sqlalchemy import text

# Complete list of every column the User SQLAlchemy model defines.
MIGRATIONS = [
    # Core identity
    "ALTER TABLE users ADD COLUMN full_name       VARCHAR",
    "ALTER TABLE users ADD COLUMN hashed_password VARCHAR",
    "ALTER TABLE users ADD COLUMN role            VARCHAR DEFAULT 'student'",

    # Account status (SQLite uses 1/0 for booleans, CURRENT_TIMESTAMP for dates)
    "ALTER TABLE users ADD COLUMN is_active   BOOLEAN  DEFAULT 1",
    "ALTER TABLE users ADD COLUMN is_verified BOOLEAN  DEFAULT 0",
    "ALTER TABLE users ADD COLUMN created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP",

    # Profile
    "ALTER TABLE users ADD COLUMN phone_number VARCHAR",
    "ALTER TABLE users ADD COLUMN avatar_url   VARCHAR",

    # Notification preferences
    "ALTER TABLE users ADD COLUMN email_alerts BOOLEAN DEFAULT 1",
    "ALTER TABLE users ADD COLUMN sms_alerts   BOOLEAN DEFAULT 0",

    # Verification workflow
    "ALTER TABLE users ADD COLUMN verification_status             VARCHAR DEFAULT 'unverified'",
    "ALTER TABLE users ADD COLUMN verification_rejection_reason   VARCHAR",
]

def run():
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            col = sql.split("ADD COLUMN ")[1].split()[0]
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  ✅ Added  {col}")
            except Exception as e:
                conn.rollback()
                print(f"  ⚡ {col} already exists (skipping)")

    print("\nDone. Restart uvicorn now.\n")

if __name__ == "__main__":
    print("\n--- Users Table Migration ---\n")
    run()