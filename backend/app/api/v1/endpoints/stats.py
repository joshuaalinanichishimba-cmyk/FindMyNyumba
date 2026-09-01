"""
Public homepage statistics.

GET /stats/home — real, live platform numbers for the homepage. Never
hardcoded; every value is a fresh COUNT/query so the homepage grows with the
platform. Also returns a few real active listings for the homepage grid (no
placeholder/fake properties).

Verified landlords use the same definition as the rest of the app: a landlord
whose verification is genuinely approved/verified.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.listing import Listing
from app.api.v1.endpoints.listings import _listing_card

router = APIRouter()


@router.get("/stats/home")
def home_stats(request: Request, db: Session = Depends(get_db)):
    active_listings = db.query(Listing).filter(Listing.status == "active").count()

    students = db.query(User).filter(User.role == "student").count()

    verified_landlords = (
        db.query(User)
        .filter(
            User.role == "landlord",
            or_(
                User.verification_status == "approved",
                User.verification_status == "verified",
                User.is_verified == True,  # noqa: E712
            ),
        )
        .count()
    )

    accommodation_assistants = (
        db.query(User).filter(User.role == "accommodation_assistant").count()
    )

    # a few real active listings for the homepage grid (never fabricated)
    rows = (
        db.query(Listing)
        .filter(Listing.status == "active")
        .order_by(
            Listing.is_boosted.desc(),      # boosted first, if any
            Listing.created_at.desc(),
        )
        .limit(6)
        .all()
    )
    featured = [_listing_card(l, request) for l in rows]

    return {
        "active_listings": active_listings,
        "students": students,
        "verified_landlords": verified_landlords,
        "accommodation_assistants": accommodation_assistants,
        "featured_listings": featured,
    }
