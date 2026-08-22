"""
backend/scripts/add_price_review.py
Stage 2 migration.

1. Adds price ANNOTATION columns to listings (market band + confidence + review
   state). listings.price itself is untouched: it stays the landlord's number.
2. Creates the price_reviews table via create_all (safe: only builds missing
   tables).

Additive and re-runnable. RUN FROM backend/ AS A MODULE so .env and app import:
  cd D:\\FindMyNyumba_Original\\backend
  C:\\Users\\Joshu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe -m scripts.add_price_review
"""
import sys
from sqlalchemy import text

from app.core.database import engine, Base
# Import so create_all knows the new table.
from app.models.price_review import PriceReview  # noqa: F401


LISTING_COLUMNS = [
    # market band implied by ACCEPTED student reviews (never the landlord price)
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS market_low DOUBLE PRECISION",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS market_high DOUBLE PRECISION",
    # unverified | low | medium | high
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS price_confidence VARCHAR DEFAULT 'unverified'",
    # unreviewed | under_review | reviewed
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS price_review_status VARCHAR DEFAULT 'unreviewed'",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS price_last_reviewed_at TIMESTAMPTZ",
    # backfill any pre-existing NULLs
    "UPDATE listings SET price_confidence = 'unverified' WHERE price_confidence IS NULL",
    "UPDATE listings SET price_review_status = 'unreviewed' WHERE price_review_status IS NULL",
]


def main():
    print("Adding price annotation columns to listings...")
    with engine.begin() as conn:
        for sql in LISTING_COLUMNS:
            print("  ->", " ".join(sql.split())[:72], "...")
            conn.execute(text(sql))

    print("Creating price_reviews table (if missing)...")
    Base.metadata.create_all(bind=engine, tables=[PriceReview.__table__])

    with engine.begin() as conn:
        cols = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'listings' AND column_name LIKE 'price%' "
            "   OR table_name = 'listings' AND column_name LIKE 'market%' "
            "ORDER BY column_name"
        )).fetchall()
        has_table = conn.execute(text(
            "SELECT to_regclass('public.price_reviews')"
        )).scalar()

    print("\nlistings price-related columns:")
    for c in cols:
        print("  -", c[0])
    print("price_reviews table:", "present" if has_table else "MISSING")
    print("\nMigration complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("MIGRATION FAILED:", type(e).__name__, e)
        sys.exit(1)
