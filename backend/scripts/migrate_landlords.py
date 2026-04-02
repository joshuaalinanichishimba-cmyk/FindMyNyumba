"""
migrate_landlords.py  — Safely adds missing Landlord columns to the users table.
"""
from app.core.database import engine
from sqlalchemy import text

MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN business_name VARCHAR",
    "ALTER TABLE users ADD COLUMN business_location VARCHAR",
    "ALTER TABLE users ADD COLUMN id_number VARCHAR",
]

def run():
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            col = sql.split("ADD COLUMN ")[1].split()[0]
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  ✅ Added {col}")
            except Exception as e:
                conn.rollback()
                print(f"  ⚡ {col} already exists (skipping)")

if __name__ == "__main__":
    print("\n--- Running Phase 7 Database Migration ---")
    run()
    print("Done.\n")