"""
backend/scripts/add_verified_price.py
Stage 2 follow-up migration.

Adds a VERIFIED MARKET PRICE to listings: FindMyNyumba's own conclusion about
fair rent, set by an admin after moderating student price reviews.

This is a SEPARATE number from listings.price. The landlord's asking price is
never overwritten. A listing can show both:
   "Landlord asking K500  -  FindMyNyumba verified fair price ~K380"

Additive, re-runnable. RUN FROM backend/ AS A MODULE:
  cd D:\\FindMyNyumba_Original\\backend
  C:\\Users\\Joshu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe -m scripts.add_verified_price
"""
import sys
from sqlalchemy import text

from app.core.database import engine


STATEMENTS = [
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verified_market_price DOUBLE PRECISION",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verified_price_set_by INTEGER",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verified_price_set_by_name VARCHAR",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS verified_price_set_at TIMESTAMPTZ",
]


def main():
    print("Adding verified market price columns to listings...")
    with engine.begin() as conn:
        for sql in STATEMENTS:
            print("  ->", " ".join(sql.split())[:72], "...")
            conn.execute(text(sql))
        cols = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'listings' AND column_name LIKE 'verified%' "
            "ORDER BY column_name"
        )).fetchall()

    print("\nlistings verified-price columns:")
    for c in cols:
        print("  -", c[0])
    print("\nMigration complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("MIGRATION FAILED:", type(e).__name__, e)
        sys.exit(1)
