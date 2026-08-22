"""
app/api/v1/endpoints/price_reviews.py
Accommodation price review workflow (Stage 2). Admin moderated.

Flow:
  student  -> POST /listings/{id}/price-review        (lands pending)
  admin    -> GET  /admin/price-reviews               (moderation queue)
  admin    -> POST /admin/price-reviews/{id}/accept    (counts + re-aggregates)
  admin    -> POST /admin/price-reviews/{id}/dismiss   (excluded)
  public   -> GET  /listings/{id}/price-insight        (confidence + band)

listings.price is NEVER written here. Accepted reviews only populate the
listing annotation fields. A price review is about accommodation rent and has
no connection to service_packages (FindMyNyumba service fees).
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.permissions import require
from app.models.user import User
from app.models.listing import Listing
from app.models.price_review import PriceReview, REVIEW_TYPES

logger = logging.getLogger("fmn.price_review")

router = APIRouter(tags=["Price Review"])

MODERATE_PERM = "reviews.moderate"   # matches Trust & Safety's reviews.* wildcard


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- aggregation
def _recompute_listing_confidence(db: Session, listing: Listing) -> None:
    """
    Reads a listing's ACCEPTED reviews and rewrites its annotation fields.
    Never touches listing.price.

    Confidence:
      unverified -> no accepted reviews
      low        -> 1-2 accepted reviews
      medium     -> 3-4
      high       -> 5+
    Market band comes from accepted reviews that cite a price (too_high /
    too_low / paid_different). confirmed_accurate endorses listing.price and
    counts toward confidence but not the band.
    """
    accepted = (db.query(PriceReview)
                  .filter(PriceReview.listing_id == listing.id,
                          PriceReview.status == "accepted")
                  .all())

    n = len(accepted)
    if n == 0:
        listing.market_low = None
        listing.market_high = None
        listing.price_confidence = "unverified"
        listing.price_review_status = "unreviewed"
        listing.price_last_reviewed_at = _now()
        return

    priced = [float(r.reported_price) for r in accepted
              if r.reported_price is not None and r.review_type != "confirmed_accurate"]
    # confirmed_accurate endorses the listed price, so fold it into the band
    if any(r.review_type == "confirmed_accurate" for r in accepted) and listing.price is not None:
        priced.append(float(listing.price))

    if priced:
        listing.market_low = min(priced)
        listing.market_high = max(priced)

    if n >= 5:
        listing.price_confidence = "high"
    elif n >= 3:
        listing.price_confidence = "medium"
    else:
        listing.price_confidence = "low"

    listing.price_review_status = "reviewed"
    listing.price_last_reviewed_at = _now()


# ---------------------------------------------------------------- student
class PriceReviewBody(BaseModel):
    review_type: str = Field(..., description="too_high | too_low | confirmed_accurate | paid_different")
    reported_price: float | None = Field(None, ge=0)
    note: str | None = Field(None, max_length=1000)


@router.post("/listings/{listing_id}/price-review", status_code=201)
def submit_price_review(listing_id: int, body: PriceReviewBody,
                        current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if body.review_type not in REVIEW_TYPES:
        raise HTTPException(status_code=400, detail="Invalid review type.")

    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # A cited price is required except when confirming the listed price is right.
    if body.review_type != "confirmed_accurate" and body.reported_price is None:
        raise HTTPException(status_code=400,
                            detail="Please include the rent amount you are reporting.")

    # One pending review per user per listing, to blunt spam.
    dup = (db.query(PriceReview)
             .filter(PriceReview.listing_id == listing_id,
                     PriceReview.user_id == current_user.id,
                     PriceReview.status == "pending")
             .first())
    if dup:
        raise HTTPException(status_code=409,
                            detail="You already have a price review pending on this listing.")

    review = PriceReview(
        listing_id=listing_id,
        user_id=current_user.id,
        review_type=body.review_type,
        reported_price=body.reported_price,
        currency="ZMW",
        note=(body.note or "").strip() or None,
        listed_price_at_review=float(listing.price) if listing.price is not None else None,
        status="pending",
    )
    db.add(review)

    # Flag the listing as under review (annotation only; price untouched).
    if getattr(listing, "price_review_status", None) in (None, "unreviewed"):
        listing.price_review_status = "under_review"

    db.commit()
    db.refresh(review)
    logger.info("price_review.submitted id=%s listing=%s type=%s user=%s",
                review.id, listing_id, body.review_type, current_user.id)
    return {"id": review.id, "status": "pending",
            "message": "Thank you. Our team will review this."}


# ---------------------------------------------------------------- public
@router.get("/listings/{listing_id}/price-insight")
def price_insight(listing_id: int, db: Session = Depends(get_db)):
    """Public. Confidence + market band. Never exposes individual reviews."""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    accepted = (db.query(PriceReview)
                  .filter(PriceReview.listing_id == listing_id,
                          PriceReview.status == "accepted")
                  .count())
    return {
        "listing_id": listing_id,
        "price": float(listing.price) if listing.price is not None else None,
        "confidence": getattr(listing, "price_confidence", None) or "unverified",
        "review_status": getattr(listing, "price_review_status", None) or "unreviewed",
        "market_low": getattr(listing, "market_low", None),
        "market_high": getattr(listing, "market_high", None),
        "verified_market_price": getattr(listing, "verified_market_price", None),
        "based_on_reviews": accepted,
    }


# ---------------------------------------------------------------- admin
def _review_dict(r: PriceReview):
    return {
        "id": r.id, "listing_id": r.listing_id, "user_id": r.user_id,
        "review_type": r.review_type,
        "reported_price": float(r.reported_price) if r.reported_price is not None else None,
        "listed_price_at_review": float(r.listed_price_at_review) if r.listed_price_at_review is not None else None,
        "currency": r.currency, "note": r.note, "status": r.status,
        "moderated_by_name": r.moderated_by_name,
        "moderated_at": r.moderated_at.isoformat() if r.moderated_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/admin/price-reviews")
def admin_list_reviews(status: str = "pending",
                       admin: User = Depends(require(MODERATE_PERM)),
                       db: Session = Depends(get_db)):
    q = db.query(PriceReview)
    if status != "all":
        q = q.filter(PriceReview.status == status)
    rows = q.order_by(PriceReview.created_at.desc()).limit(200).all()
    return [_review_dict(r) for r in rows]


class ModerateBody(BaseModel):
    note: str | None = Field(None, max_length=1000)


def _moderate(db, review_id, admin, decision, note):
    review = db.query(PriceReview).filter(PriceReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review.status != "pending":
        raise HTTPException(status_code=409,
                            detail=f"This review was already {review.status}.")

    review.status = decision
    review.moderated_by = admin.id
    review.moderated_by_name = getattr(admin, "full_name", None)
    review.moderated_at = _now()
    review.moderation_note = (note or "").strip() or None
    db.commit()

    listing = db.query(Listing).filter(Listing.id == review.listing_id).first()
    if listing:
        _recompute_listing_confidence(db, listing)
        db.commit()

    logger.info("price_review.%s id=%s listing=%s by=%s",
                decision, review_id, review.listing_id, admin.id)
    return review, listing


@router.post("/admin/price-reviews/{review_id}/accept")
def accept_review(review_id: int, body: ModerateBody = ModerateBody(),
                  admin: User = Depends(require(MODERATE_PERM)),
                  db: Session = Depends(get_db)):
    review, listing = _moderate(db, review_id, admin, "accepted", body.note)
    return {"id": review.id, "status": "accepted",
            "listing_confidence": getattr(listing, "price_confidence", None) if listing else None}


@router.post("/admin/price-reviews/{review_id}/dismiss")
def dismiss_review(review_id: int, body: ModerateBody = ModerateBody(),
                   admin: User = Depends(require(MODERATE_PERM)),
                   db: Session = Depends(get_db)):
    review, listing = _moderate(db, review_id, admin, "dismissed", body.note)
    return {"id": review.id, "status": "dismissed"}


import statistics


def _median_of_accepted(db: Session, listing_id: int):
    """Median reported price across accepted reviews that cite a price."""
    rows = (db.query(PriceReview)
              .filter(PriceReview.listing_id == listing_id,
                      PriceReview.status == "accepted",
                      PriceReview.reported_price.isnot(None))
              .all())
    prices = [float(r.reported_price) for r in rows
              if r.review_type != "confirmed_accurate"]
    if not prices:
        return None, 0
    return round(statistics.median(prices), 2), len(prices)


@router.get("/admin/listings/{listing_id}/price-review-detail")
def price_review_detail(listing_id: int,
                        admin: User = Depends(require(MODERATE_PERM)),
                        db: Session = Depends(get_db)):
    """
    Everything an admin needs to set a verified price: the listing's asking
    price, its accepted reviews, the suggested median, and any verified price
    already set.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    accepted = (db.query(PriceReview)
                  .filter(PriceReview.listing_id == listing_id,
                          PriceReview.status == "accepted")
                  .order_by(PriceReview.created_at.desc())
                  .all())
    median, n_priced = _median_of_accepted(db, listing_id)

    return {
        "listing_id": listing_id,
        "asking_price": float(listing.price) if listing.price is not None else None,
        "confidence": getattr(listing, "price_confidence", None) or "unverified",
        "verified_market_price": getattr(listing, "verified_market_price", None),
        "verified_price_set_by_name": getattr(listing, "verified_price_set_by_name", None),
        "verified_price_set_at": (listing.verified_price_set_at.isoformat()
                                  if getattr(listing, "verified_price_set_at", None) else None),
        "suggested_price": median,
        "based_on_priced_reviews": n_priced,
        "accepted_reviews": [_review_dict(r) for r in accepted],
    }


class VerifiedPriceBody(BaseModel):
    verified_market_price: float | None = Field(..., ge=0,
        description="Set the FindMyNyumba verified fair price. Null clears it.")


@router.post("/admin/listings/{listing_id}/verified-price")
def set_verified_price(listing_id: int, body: VerifiedPriceBody,
                       admin: User = Depends(require(MODERATE_PERM)),
                       db: Session = Depends(get_db)):
    """
    Set (or clear) the FindMyNyumba verified market price on a listing.

    SEPARATION RULE: listings.price (the landlord's asking price) is NEVER
    written here. verified_market_price is a distinct annotation, shown
    alongside the landlord's price, representing FindMyNyumba's own conclusion.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    listing.verified_market_price = body.verified_market_price
    if hasattr(listing, "verified_price_set_by"):
        listing.verified_price_set_by = admin.id
    if hasattr(listing, "verified_price_set_by_name"):
        listing.verified_price_set_by_name = getattr(admin, "full_name", None)
    if hasattr(listing, "verified_price_set_at"):
        listing.verified_price_set_at = _now() if body.verified_market_price is not None else None

    db.commit()
    logger.info("verified_price.set listing=%s value=%s by=%s",
                listing_id, body.verified_market_price, admin.id)
    return {
        "listing_id": listing_id,
        "asking_price": float(listing.price) if listing.price is not None else None,
        "verified_market_price": listing.verified_market_price,
    }


# ============================================================
