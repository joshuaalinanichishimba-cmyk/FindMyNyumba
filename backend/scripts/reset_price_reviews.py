"""
backend/scripts/reset_price_reviews.py
Reset the price-review state of one or more listings.

Deletes every price_reviews row for the given listing ids and resets that
listing's annotation fields back to their untouched defaults
(unverified / unreviewed / null band). listings.price is never modified.

Use it to clear TEST data off a real listing before launch, or to fully
re-do a listing's review history.

RUN FROM backend/ AS A MODULE:
  cd D:\\FindMyNyumba_Original\\backend
  # one or more listing ids as arguments:
  C:\\Users\\Joshu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe -m scripts.reset_price_reviews 3
  C:\\Users\\Joshu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe -m scripts.reset_price_reviews 3 18 26
"""
import sys

from app.core.database import SessionLocal
from app.models.listing import Listing
from app.models.price_review import PriceReview


def reset(listing_ids):
    db = SessionLocal()
    try:
        for lid in listing_ids:
            listing = db.query(Listing).filter(Listing.id == lid).first()
            if not listing:
                print(f"  listing {lid}: NOT FOUND, skipping")
                continue

            n = (db.query(PriceReview)
                   .filter(PriceReview.listing_id == lid)
                   .delete(synchronize_session=False))

            listing.market_low = None
            listing.market_high = None
            listing.price_confidence = "unverified"
            listing.price_review_status = "unreviewed"
            listing.price_last_reviewed_at = None
            if hasattr(listing, "verified_market_price"):
                listing.verified_market_price = None
                listing.verified_price_set_by = None
                listing.verified_price_set_by_name = None
                listing.verified_price_set_at = None

            db.commit()
            print(f"  listing {lid}: deleted {n} review(s), annotations reset "
                  f"(price left at {listing.price})")
    finally:
        db.close()


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python -m scripts.reset_price_reviews <listing_id> [more ids...]")
        sys.exit(1)
    try:
        ids = [int(a) for a in args]
    except ValueError:
        print("All arguments must be integer listing ids.")
        sys.exit(1)

    print(f"Resetting price reviews for listing ids: {ids}")
    reset(ids)
    print("Done.")


if __name__ == "__main__":
    main()
