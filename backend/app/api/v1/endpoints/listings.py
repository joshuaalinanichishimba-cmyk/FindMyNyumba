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

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.models.listing import Listing
from app.models.listing_media import ListingMedia
from app.models.report import Report
from app.models.review import Review
from app.models.viewing_request import ViewingRequest, ViewingStatus
from app.models.user import User

router = APIRouter(prefix="/properties", tags=["Properties"])


# â”€â”€ Request models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ReviewCreate(BaseModel):
    rating:  int            = Field(..., ge=1, le=5)
    comment: str            = Field(..., min_length=1, max_length=2000)
    rating_accuracy: Optional[int] = Field(None, ge=1, le=5)
    rating_landlord: Optional[int] = Field(None, ge=1, le=5)
    rating_value:    Optional[int] = Field(None, ge=1, le=5)


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
        "available_spots": l.available_spots,
        "total_spots": l.total_spots,
        "availability_status": l.availability_status,
        "view_count": getattr(l, "_view_count", 0),
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

    # Batch view counts (one grouped query for the whole page) -> attach _view_count
    _ids = [l.id for l in listings]
    if _ids:
        from app.models.listing_event import ListingEvent
        from sqlalchemy import func as _func
        _counts = dict(
            db.query(ListingEvent.listing_id, _func.count(ListingEvent.id))
              .filter(ListingEvent.listing_id.in_(_ids), ListingEvent.kind == "view")
              .group_by(ListingEvent.listing_id).all()
        )
        for _l in listings:
            _l._view_count = _counts.get(_l.id, 0)
    # Anonymous search logging (analytics) - only real searches, never break browse.
    if q or university or (min_price is not None) or (max_price is not None):
        try:
            from app.models.search_log import SearchLog
            db.add(SearchLog(
                query=(q.strip() if q else None),
                university=(university.strip() if university else None),
                min_price=min_price, max_price=max_price,
                results_count=len(listings),
            ))
            db.commit()
        except Exception:
            db.rollback()
    return [_listing_card(l, request) for l in listings]


# â”€â”€ GET /properties/{id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _student_has_paid_access(db, user_id) -> bool:
    """True if the user has a successful verification_fee payment in the last 30 days."""
    if not user_id:
        return False
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    from app.models.admin_models import Transaction
    cutoff = _dt.now(_tz.utc) - _td(days=30)
    txn = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.type == "verification_fee",
        Transaction.status == "success",
        Transaction.created_at >= cutoff,
    ).first()
    return txn is not None


@router.get("/{listing_id}")
def get_listing_detail(
    listing_id: int,
    request:    Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
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
        }
        _uid = current_user.id if current_user else None
        _can_see_contact = (
            _student_has_paid_access(db, _uid)
            or (_uid is not None and _uid == owner.id)
            or (current_user is not None and getattr(current_user, "role", "") == "admin")
        )
        owner_data["phone_number"] = owner.phone_number if _can_see_contact else None
        owner_data["contact_locked"] = not _can_see_contact

    _detail_view_count = 0
    try:
        from sqlalchemy import func as _func
        _detail_view_count = db.query(_func.count(ListingEvent.id)).filter(
            ListingEvent.listing_id == listing.id, ListingEvent.kind == "view"
        ).scalar() or 0
    except Exception:
        _detail_view_count = 0
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
        "available_spots":     listing.available_spots,
        "total_spots":         listing.total_spots,
        "availability_status": listing.availability_status,
        "view_count":          _detail_view_count,
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
    # GATE: a student may only review a property they actually completed a viewing for.
    # Completion required the landlord to verify the student's code in person, so every
    # review is tied to a real, verified visit (anti-fake-review core).
    completed_viewing = (
        db.query(ViewingRequest)
          .filter(
              ViewingRequest.student_id == current_user.id,
              ViewingRequest.listing_id == listing_id,
              ViewingRequest.status == ViewingStatus.COMPLETED.value,
          )
          .first()
    )
    if not completed_viewing:
        raise HTTPException(
            status_code=403,
            detail="You can only review a property after completing a viewing of it.",
        )
    existing = db.query(Review).filter(Review.listing_id == listing_id, Review.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this listing.")
    row = Review(listing_id=listing_id, user_id=current_user.id, user_name=current_user.full_name, rating=review.rating, comment=review.comment.strip(), status="pending", rating_accuracy=review.rating_accuracy, rating_landlord=review.rating_landlord, rating_value=review.rating_value)
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


# -- GET /properties/{id}/reviews (public, trust-enriched) -------------------
# Returns APPROVED reviews for a listing, each enriched with reviewer trust
# signals: verification badge, account age (member_since), avatar + id (for a
# profile popup), and verified_viewing (true because reviews are gated on a
# completed, code-verified viewing of THIS listing -> anti-fake signal).
@router.get("/{listing_id}/reviews")
def list_property_reviews(listing_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Review)
          .filter(Review.listing_id == listing_id, Review.status == "approved")
          .order_by(Review.created_at.desc())
          .all()
    )
    out = []
    for r in rows:
        u = db.query(User).filter(User.id == r.user_id).first()
        visited = db.query(ViewingRequest).filter(
            ViewingRequest.student_id == r.user_id,
            ViewingRequest.listing_id == listing_id,
            ViewingRequest.status == ViewingStatus.COMPLETED.value,
        ).first() is not None
        out.append({
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewer_id": r.user_id,
            "reviewer_name": (u.full_name if u else r.user_name) or "Student",
            "reviewer_verified": bool(u and ((u.verification_status == "approved") or u.is_verified)),
            "reviewer_member_since": u.created_at.isoformat() if (u and u.created_at) else None,
            "reviewer_avatar": u.avatar_url if u else None,
            "verified_viewing": visited,
            "reply_text": r.reply_text,
            "reply_at": r.reply_at.isoformat() if r.reply_at else None,
            "rating_accuracy": r.rating_accuracy,
            "rating_landlord": r.rating_landlord,
            "rating_value": r.rating_value,
        })
    avg = round(sum(x["rating"] for x in out) / len(out), 1) if out else None
    return {"count": len(out), "average": avg, "reviews": out}


# -- POST /properties/reviews/{id}/report -----------------------------------
# Any logged-in user can flag a review as fake/abusive. Sets status to
# "flagged" -> immediately hidden from public (GET returns only "approved")
# and surfaced in the admin queue (GET /admin/reviews?status=flagged) for a
# human decision (re-approve if legit, reject if genuinely bad).
@router.post("/reviews/{review_id}/report", status_code=200)
def report_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found.")
    # Don't let someone "report" to escalate their own already-removed review, etc.
    if r.status == "flagged":
        return {"status": "reported", "message": "This review is already under review."}
    r.status = "flagged"
    db.commit()
    return {"status": "reported", "message": "Thank you. Our team will review this report."}


# -- POST /properties/reviews/{id}/reply ------------------------------------
# The listing OWNER (the host being reviewed) may post one public reply per
# review (editable). This gives the paying side a fair right of response and
# signals an engaged, real host. Ownership: the review's listing.owner_id must
# match the caller.
class ReplyBody(BaseModel):
    text: str


@router.post("/reviews/{review_id}/reply", status_code=200)
def reply_to_review(
    review_id: int,
    body: ReplyBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found.")
    listing = db.query(Listing).filter(Listing.id == r.listing_id).first()
    if not listing or listing.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the listing owner can reply to this review.")
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Reply cannot be empty.")
    if len(text) > 1000:
        raise HTTPException(status_code=400, detail="Reply is too long (max 1000 characters).")
    from datetime import datetime, timezone
    r.reply_text = text
    r.reply_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok", "reply_text": r.reply_text, "reply_at": r.reply_at.isoformat()}

@router.get("/{listing_id}/history")
def get_property_history(listing_id: int, db: Session = Depends(get_db)):
    """Public, transparency-focused timeline. Real dated events only (no reports)."""
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.status == "active").first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    owner = db.query(User).filter(User.id == listing.owner_id).first()
    events = []
    if listing.created_at:
        events.append({"date": listing.created_at.isoformat(), "icon": "calendar-plus",
                       "label": "Listed on FindMyNyumba", "kind": "listed"})
    if owner and owner.created_at:
        events.append({"date": owner.created_at.isoformat(), "icon": "user-plus",
                       "label": "Host joined FindMyNyumba", "kind": "host_joined"})
    fr = (db.query(Review).filter(Review.listing_id == listing_id, Review.status == "approved")
            .order_by(Review.created_at.asc()).first())
    if fr and fr.created_at:
        events.append({"date": fr.created_at.isoformat(), "icon": "star",
                       "label": "First verified review received", "kind": "first_review"})
    completed = (db.query(ViewingRequest)
                   .filter(ViewingRequest.listing_id == listing_id,
                           ViewingRequest.status == ViewingStatus.COMPLETED.value)
                   .all())
    if completed:
        n = len(completed)
        dated = [c.completed_at for c in completed if c.completed_at]
        when = max(dated).isoformat() if dated else listing.created_at.isoformat()
        events.append({"date": when, "icon": "handshake",
                       "label": str(n) + (" viewings completed" if n != 1 else " viewing completed"),
                       "kind": "viewings"})
    events.sort(key=lambda e: e["date"])
    return {"events": events,
            "host_verified": bool(owner and (owner.verification_status or "") == "verified")}

@router.get("/host/{owner_id}/response-stats")
def get_host_response_stats(owner_id: int, db: Session = Depends(get_db)):
    """Public, fully-transparent host response metrics. Threshold-gated for integrity."""
    from app.models.message import Message
    import statistics as _stats
    msgs = (db.query(Message)
              .filter((Message.sender_id == owner_id) | (Message.receiver_id == owner_id))
              .order_by(Message.created_at.asc()).all())
    threads = {}
    for m in msgs:
        other = m.receiver_id if m.sender_id == owner_id else m.sender_id
        threads.setdefault(other, []).append((m.sender_id, m.created_at))
    total_inquiries = 0
    responded = 0
    response_times = []
    for student_id, events in threads.items():
        inquiry_at = next((t for (s, t) in events if s == student_id), None)
        if not inquiry_at:
            continue
        total_inquiries += 1
        reply_at = next((t for (s, t) in events if s == owner_id and t and t > inquiry_at), None)
        if reply_at:
            responded += 1
            response_times.append((reply_at - inquiry_at).total_seconds())
    owner_listing_ids = [l.id for l in db.query(Listing.id).filter(Listing.owner_id == owner_id).all()]
    comm_vals = []
    if owner_listing_ids:
        rows = (db.query(Review.rating_landlord)
                  .filter(Review.listing_id.in_(owner_listing_ids),
                          Review.status == "approved",
                          Review.rating_landlord.isnot(None)).all())
        comm_vals = [r[0] for r in rows if r[0]]
    median_secs = _stats.median(response_times) if response_times else None
    return {
        "enough_data": total_inquiries >= 3,
        "total_inquiries": total_inquiries,
        "response_rate": round(100 * responded / total_inquiries) if total_inquiries else None,
        "median_response_seconds": int(median_secs) if median_secs is not None else None,
        "communication_quality": round(sum(comm_vals)/len(comm_vals), 1) if comm_vals else None,
        "communication_count": len(comm_vals),
    }
