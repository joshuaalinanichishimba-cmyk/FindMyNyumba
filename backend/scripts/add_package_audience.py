"""
backend/scripts/add_package_audience.py
One time migration: adds `audience` and `grant_type` to service_packages.

WHY A SCRIPT AND NOT create_all():
create_all() only creates MISSING TABLES. It never adds columns to a table
that already exists, so a new model field on service_packages would silently
never appear in the database.

Both columns are additive with safe defaults, so this is non destructive and
re-runnable. Existing rows are backfilled as student facing packages, which is
exactly what they are today.

RUN FROM backend/ SO .env LOADS:
  cd D:\\FindMyNyumba_Original\\backend
  C:\\Users\\Joshu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe scripts\\add_package_audience.py
"""
import sys
from sqlalchemy import text

from app.core.database import engine


STATEMENTS = [
    # audience: who buys this package. Controls which public page shows it.
    """ALTER TABLE service_packages
       ADD COLUMN IF NOT EXISTS audience VARCHAR DEFAULT 'student'""",

    # grant_type: what a successful purchase actually unlocks.
    #   student_access -> messaging + landlord contact for duration_days
    #   listing_boost  -> time boxed featured placement on the buyer's listings
    """ALTER TABLE service_packages
       ADD COLUMN IF NOT EXISTS grant_type VARCHAR DEFAULT 'student_access'""",

    # Backfill any pre-existing NULLs from before the defaults existed.
    """UPDATE service_packages SET audience = 'student' WHERE audience IS NULL""",
    """UPDATE service_packages SET grant_type = 'student_access' WHERE grant_type IS NULL""",
]


def main():
    print("Connecting to the database...")
    with engine.begin() as conn:
        for sql in STATEMENTS:
            label = " ".join(sql.split())[:70]
            print("  ->", label, "...")
            conn.execute(text(sql))

        rows = conn.execute(text(
            "SELECT code, audience, grant_type, is_active "
            "FROM service_packages ORDER BY sort_order"
        )).fetchall()

    print("\nservice_packages now reads:")
    for r in rows:
        print(f"  {r[0]:<20} audience={r[1]:<10} grant={r[2]:<16} active={r[3]}")
    print("\nMigration complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("MIGRATION FAILED:", type(e).__name__, e)
        sys.exit(1)
