"""
app/api/v1/endpoints/listings.py

Public listing endpoints used by browse.html, listing.html, and the
search bars on every dashboard.

FIXES vs original:
- Image URLs are now resolved to ABSOLUTE URLs on the backend (using the
  request's host) before being returned. The original returned bare
  paths like "/static/uploads/properties/x.jpg" which forced every
  frontend page to invent a "guess the backend host" helper. Several of
  those guess functions were broken (URL-inside-URL 404s).
- GET /properties is paginated by default (limit/offset) so a future
  10K-listing browse page doesn't dump a multi-MB JSON blob to mobile.
- Trim/clamp on filter inputs prevents nuisance crashes from oversized
  or malformed query strings.
- Review submission no longer silently lies. Until a Review model is
  added, the endpoint is explicit that nothing is persisted, and the
  payload is validated so future wiring is one-line.
- Report endpoint deduplicates: a single user can only have one open
  (pending) report per listing, preventing trivial spam.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.listing import Listing
from app.models.listing_media import ListingMedia
from app.models.report import Report
from app.models.review import Review
from app.models.user import User

router = APIRouter(prefix="/properties", tags=["Properties"])


# â”€â”€ Request models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ReviewCreate(BaseModel):
    rating:  int            = Field(..., ge=1, le=5)
    comment: str            = Field(..., min_length=1, max_length=2000)


class ReportCreate(BaseModel):
    reason:      str            = Field(..., min_length=1, max_length=120)
    description: Optional[str]  = Field(None, max_length=2000)


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _absolute_image_url(raw: Optional[str], request: Request) -> Optional[str]:
    """
    Convert whatever is stored in Listing.image_url into an absolute URL the
    browser can use directly. Three input cases:
      1. None / empty            â†’ None (frontend uses placeholder)
      2. Already a full URL      â†’ returned as-is
      3. Bare filename or path   â†’ prefixed with the API host + static path
    """
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    # Build absolute URL from the request scheme/host so this works in every
    # deployment without code changes (localhost, render, custom domain).
    base = str(request.base_url).rstrip("/")  # e.g. "https://api.findmynyumba.com"
    if raw.startswith("/"):
        return f"{base}{raw}"
    return f"{base}/static/uploads/properties/{raw}"


def _watermark(url):
    """Add a FindMyNyumba watermark to a Cloudinary IMAGE url.
    Idempotent; skips empties, non-Cloudinary urls, videos, and already-marked urls."""
    if not url or "res.cloudinary.com" not in url or "/image/upload/" not in url:
        return url
    if "l_text:" in url:
        return url
    wm = "l_text:Arial_70_bold:FindMyNyumba,co_white,o_20,g_center"
    return url.replace("/image/upload/", f"/image/upload/{wm}/", 1)


def _media_response(m, request: Request) -> dict:
    return {
        "id": m.id,
        "listing_id": m.listing_id,
        "media_url": (_watermark(_absolute_image_url(m.media_url, request)) if m.media_type == "photo" else _absolute_image_url(m.media_url, request)),
        "media_type": m.media_type,
        "public_id": m.public_id,
        "width": m.width,
        "height": m.height,
        "duration": m.duration,
        "position": m.position,
        "is_cover": m.is_cover,
    }


def _listing_card(l: Listing, request: Request) -> dict:
    """Compact representation for browse and dashboard grids."""
    return {
        "id":         l.id,
        "title":      l.title,
        "price":      l.price,
        "location":   l.location,
        "is_boosted": l.is_boosted,
        "image_url":  _watermark(_absolute_image_url(l.image_url, request)),
        "media":      [_media_response(m, request) for m in (l.media or [])],
        "cover_url":  _watermark(_absolute_image_url(l.cover_url, request)),
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


# â”€â”€ GET /properties â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("")
@router.get("/")
def get_all_properties(
    request:    Request,
    q:          Optional[str]   = Query(None, max_length=120),
    min_price:  Optional[float] = Query(None, ge=0),
    max_price:  Optional[float] = Query(None, ge=0),
    university: Optional[str]   = Query(None, max_length=80),
    limit:      int             = Query(60, ge=1, le=200),
    offset:     int             = Query(0,  ge=0),
    db: Session = Depends(get_db),
):
    """
    Public browse endpoint. Returns only 'active' listings. Boosted listings
    appear first, then newest. Paginated via limit/offset; defaults are
    generous enough that the existing browse page works unchanged.
    """
    query = db.query(Listing).filter(Listing.status == "active")

    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            Listing.title.ilike(term)
            | Listing.location.ilike(term)
            | Listing.description.ilike(term)
        )

    if min_price is not None:
        query = query.filter(Listing.price >= min_price)
    if max_price is not None:
        query = query.filter(Listing.price <= max_price)
    if university:
        query = query.filter(Listing.location.ilike(f"%{university.strip()}%"))

    listings = (
        query.order_by(Listing.is_boosted.desc(), Listing.created_at.desc())
             .offset(offset)
             .limit(limit)
             .all()
    )

    return [_listing_card(l, request) for l in listings]


# â”€â”€ GET /properties/{id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/{listing_id}")
def get_listing_detail(
    listing_id: int,
    request:    Request,
    db: Session = Depends(get_db),
):
    """
    Public detail endpoint. Returns full info plus owner card data.
    listing.html uses owner.full_name, owner.role, owner.verification_status.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # Don't expose pending/rejected listings to the public.
    if listing.status != "active":
        raise HTTPException(status_code=404, detail="Listing not found.")

    owner = db.query(User).filter(User.id == listing.owner_id).first()

    # Fire-and-forget view tracking â€” never let it break the public page.
    try:
        from app.models.listing_event import ListingEvent
        db.add(ListingEvent(listing_id=listing.id, kind="view"))
        db.commit()
    except Exception:
        db.rollback()

    owner_data = None
    if owner:
        _listings_count = db.query(Listing).filter(
            Listing.owner_id == owner.id, Listing.status == "active"
        ).count()
        owner_data = {
            "id":                  owner.id,
            "full_name":           owner.full_name,
            "role":                owner.role,
            "verification_status": owner.verification_status or "unverified",
            "avatar_url":          owner.avatar_url,
            "member_since":        owner.created_at.isoformat() if owner.created_at else None,
            "listings_count":      _listings_count,
            "phone_number":        owner.phone_number,
        }

    return {
        "id":          listing.id,
        "title":       listing.title,
        "description": listing.description or "",
        "price":       listing.price,
        "location":    listing.location,
        "image_url":   _watermark(_absolute_image_url(listing.image_url, request)),
        "media":       [_media_response(m, request) for m in (listing.media or [])],
        "cover_url":   _watermark(_absolute_image_url(listing.cover_url, request)),
        "is_boosted":  listing.is_boosted,
        "status":      listing.status,
        "owner_id":    listing.owner_id,
        "owner":       owner_data,
        "created_at":  listing.created_at.isoformat() if listing.created_at else None,
    }


# â”€â”€ POST /properties/{id}/reviews â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.post("/{listing_id}/reviews", status_code=201)
def post_review(
    listing_id: int,
    review: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot review your own listing.")
    existing = db.query(Review).filter(Review.listing_id == listing_id, Review.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this listing.")
    row = Review(listing_id=listing_id, user_id=current_user.id, user_name=current_user.full_name, rating=review.rating, comment=review.comment.strip(), status="pending")
    db.add(row)
    db.commit()
    return {"status": "submitted", "message": "Thank you! Your review will appear after approval."}



# â”€â”€ POST /properties/{id}/report â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.post("/{listing_id}/report", status_code=201)
def report_property(
    listing_id: int,
    report: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # Prevent obvious spam: one open report per (user, listing) pair.
    existing = (
        db.query(Report)
          .filter(
              Report.reporter_id == current_user.id,
              Report.listing_id  == listing_id,
              Report.status      == "pending",
          )
          .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending report on this listing. Our team is reviewing it.",
        )

    new_report = Report(
        reporter_id = current_user.id,
        listing_id  = listing_id,
        reason      = report.reason.strip(),
        description = (report.description or "").strip() or None,
        status      = "pending",
    )
    db.add(new_report)
    db.commit()
    return {"status": "success", "message": "Report submitted. Our team will review it shortly."}
