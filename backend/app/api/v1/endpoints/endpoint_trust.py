"""
app/api/v1/endpoints/trust.py

PUBLIC Trust & Safety read endpoints (no auth required — these power the
banners and badges every visitor sees).

Routes (mounted under /api/v1):
    GET /trust/banners?page=home          -> active rotating safety banners
    GET /trust/badges/user/{user_id}      -> resolved badge for a user
    GET /trust/badges/listing/{id}        -> resolved badge for a listing

Read-only and cache-friendly. No state changes happen here, so no rate limit
beyond the global app limiter is needed; a short cache header keeps load low.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.badges import user_badge, listing_badge
from app.models.user import User
from app.models.listing import Listing
from app.models.trust_models import TrustBanner
from app.schemas.trust import TrustBannerOut, BadgeOut

router = APIRouter(prefix="/trust", tags=["Trust & Safety"])


# Sensible defaults so the banner strip is never empty, even before an admin
# adds any rows. These are returned only when the DB has no active banners.
_DEFAULT_BANNERS = [
    {"id": -1, "message": "Never pay before physically viewing a property.",
     "level": "warning", "icon": "🟢", "pages": "all", "sort_order": 0},
    {"id": -2, "message": "FindMyNyumba does not support viewing fees.",
     "level": "warning", "icon": "🟢", "pages": "all", "sort_order": 1},
    {"id": -3, "message": "Report suspicious listings immediately.",
     "level": "info", "icon": "🟢", "pages": "all", "sort_order": 2},
    {"id": -4, "message": "Verify landlord badges before sending money.",
     "level": "info", "icon": "🟢", "pages": "all", "sort_order": 3},
    {"id": -5, "message": "Always inspect accommodation before making payment.",
     "level": "warning", "icon": "🟢", "pages": "all", "sort_order": 4},
]


@router.get("/banners", response_model=list[TrustBannerOut])
def get_banners(
    response: Response,
    page: str = Query("all", max_length=40),
    db: Session = Depends(get_db),
):
    """Active banners for a page key, newest policy first. Falls back to a
    built-in safety set so the strip is never blank."""
    rows = (
        db.query(TrustBanner)
        .filter(TrustBanner.is_active.is_(True))
        .order_by(TrustBanner.sort_order.asc(), TrustBanner.id.asc())
        .all()
    )

    def _shows_on(banner_pages: str) -> bool:
        if not banner_pages or banner_pages == "all":
            return True
        keys = {p.strip() for p in banner_pages.split(",")}
        return page == "all" or page in keys

    visible = [r for r in rows if _shows_on(r.pages)]
    # 5-minute client cache: copy changes don't need to be instant.
    response.headers["Cache-Control"] = "public, max-age=300"

    if visible:
        return visible
    return _DEFAULT_BANNERS  # validated against TrustBannerOut on the way out


@router.get("/badges/user/{user_id}", response_model=BadgeOut)
def get_user_badge(user_id: int, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    response.headers["Cache-Control"] = "public, max-age=120"
    return user_badge(db, user)


@router.get("/badges/listing/{listing_id}", response_model=BadgeOut)
def get_listing_badge(listing_id: int, response: Response, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    response.headers["Cache-Control"] = "public, max-age=120"
    return listing_badge(db, listing)
