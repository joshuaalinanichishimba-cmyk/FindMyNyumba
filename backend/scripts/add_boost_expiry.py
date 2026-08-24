"""
backend/scripts/add_boost_expiry.py
Landlord Boost (Option A) migration.

listings.is_boosted already exists (a permanent boolean). This adds the expiry
so a boost is TIME-BOXED: it turns itself off when boost_expires_at passes, with
no manual cleanup - the search query filters on expiry directly.

Also (optional) records which tier and when, for admin visibility.

Additive, re-runnable. RUN FROM backend/ AS A MODULE:
  cd D:\\FindMyNyumba_Original\\backend
  C:\\Users\\Joshu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe -m scripts.add_boost_expiry
"""
import sys
from sqlalchemy import text

from app.core.database import engine


STATEMENTS = [
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS boost_expires_at TIMESTAMPTZ",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS boost_tier VARCHAR",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS boosted_at TIMESTAMPTZ",
]


def main():
    print("Adding boost expiry columns to listings...")
    with engine.begin() as conn:
        for sql in STATEMENTS:
            print("  ->", " ".join(sql.split())[:70], "...")
            conn.execute(text(sql))

        # Safety: report any listings currently boosted with NO expiry.
        # These are permanent pins from before this migration - worth reviewing.
        stale = conn.execute(text(
            "SELECT id, title FROM listings "
            "WHERE is_boosted = TRUE AND boost_expires_at IS NULL"
        )).fetchall()

        cols = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='listings' AND column_name LIKE 'boost%'"
            "ORDER BY column_name"
        )).fetchall()

    print("\nboost columns on listings:")
    for c in cols:
        print("  -", c[0])

    if stale:
        print(f"\n  NOTE: {len(stale)} listing(s) are is_boosted=TRUE with no expiry")
        print("  (permanent pins). They will stay pinned until given an expiry or")
        print("  turned off. Review:")
        for r in stale:
            print(f"    id={r[0]}  {r[1]}")
    else:
        print("\n  No permanent (no-expiry) boosts found. Clean.")
    print("\nMigration complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("MIGRATION FAILED:", type(e).__name__, e)
        sys.exit(1)
