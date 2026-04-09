"""
app/api/v1/endpoints/properties.py

Public-facing property endpoints — no auth required.
Used by:
  - browse.html  → GET /properties?q=&min_price=&max_price=&sort=
  - listing.html → GET /properties/{id}

Only "active" listings are returned to the public.
Boosted listings are sorted to the top.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.listing import Listing
from app.models.user import User

router = APIRouter(prefix="/properties", tags=["Properties"])


def _fmt(listing: Listing, owner: Optional[User] = None) -> dict:
    return {
        "id":          listing.id,
        "title":       listing.title,
        "description": listing.description,
        "price":       listing.price,
        "location":    listing.location,
        "image_url":   f"/static/uploads/properties/{listing.image_url}" if listing.image_url else None,
        "is_boosted":  listing.is_boosted,
        "status":      listing.status,
        "created_at":  listing.created_at.isoformat() if listing.created_at else None,
        "owner_id":    listing.owner_id,
        "owner_name":  owner.full_name if owner else None,
        "owner_role":  owner.role if owner else None,
        "is_verified": owner.is_verified if owner else False,
    }


@router.get("")
def browse_properties(
    q:         Optional[str]   = Query(None, description="Search keyword"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort:      Optional[str]   = Query("newest", enum=["newest", "price_asc", "price_desc"]),
    db: Session = Depends(get_db),
):
    """
    Public browse endpoint. Returns only active listings.
    Boosted listings are always first.
    Supports keyword search across title, description, and location.
    """
    query = db.query(Listing).filter(Listing.status == "active")

    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            Listing.title.ilike(term)
            | Listing.description.ilike(term)
            | Listing.location.ilike(term)
        )

    if min_price is not None:
        query = query.filter(Listing.price >= min_price)
    if max_price is not None:
        query = query.filter(Listing.price <= max_price)

    if sort == "price_asc":
        query = query.order_by(Listing.is_boosted.desc(), Listing.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Listing.is_boosted.desc(), Listing.price.desc())
    else:
        query = query.order_by(Listing.is_boosted.desc(), Listing.created_at.desc())

    listings = query.limit(100).all()

    result = []
    for l in listings:
        owner = db.query(User).filter(User.id == l.owner_id).first()
        result.append(_fmt(l, owner))

    return result


@router.get("/{listing_id}")
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    """
    Returns a single listing by ID.
    Returns active listings publicly; used by listing.html and contact-landlord.html.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing.status != "active":
        raise HTTPException(status_code=404, detail="This listing is not currently available.")

    owner = db.query(User).filter(User.id == listing.owner_id).first()
    return _fmt(listing, owner)
