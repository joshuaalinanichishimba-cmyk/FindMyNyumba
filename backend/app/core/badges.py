"""
app/core/badges.py

Single source of truth for which verification badge a user or listing earns.
Both the public read API and the admin views call these so the badge a student
sees on a card always matches the badge on the profile.

Badge ladder (highest first):
    green   verified_landlord    Landlord passed full NRC + selfie review
    green   verified_property    This specific listing passed property review
    yellow  phone_verified       Phone confirmed, identity not yet reviewed
    yellow  identity_submitted   Documents uploaded, awaiting review
    red     unverified           Nothing confirmed — treat with caution
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.listing import Listing
from app.models.trust_models import Verification, PropertyVerification

_BADGE = {
    "verified_landlord": ("Verified Landlord", "green"),
    "verified_property": ("Verified Property", "green"),
    "phone_verified":    ("Phone Verified", "yellow"),
    "identity_submitted":("Identity Submitted", "yellow"),
    "unverified":        ("Unverified", "red"),
}


def _badge(key: str) -> dict:
    label, level = _BADGE[key]
    return {"key": key, "label": label, "level": level}


def user_badge(db: Session, user: User) -> dict:
    """Resolve the strongest badge a user currently holds."""
    latest = (
        db.query(Verification)
        .filter(Verification.user_id == user.id)
        .order_by(Verification.created_at.desc())
        .first()
    )

    # Fully approved landlord/host -> green.
    if (getattr(user, "verification_status", None) == "approved"
            or getattr(user, "is_verified", False) and user.role in ("landlord", "student_host")) \
            or (latest and latest.status == "approved"):
        if user.role in ("landlord", "student_host"):
            return _badge("verified_landlord")

    # Documents submitted, under review -> yellow.
    if latest and latest.status in ("pending", "review") and (
        latest.nrc_front_uploaded or latest.selfie_uploaded
    ):
        return _badge("identity_submitted")

    # Phone confirmed only -> yellow.
    if latest and latest.phone_verified:
        return _badge("phone_verified")
    if getattr(user, "phone_number", None) and getattr(user, "is_verified", False):
        return _badge("phone_verified")

    return _badge("unverified")


def listing_badge(db: Session, listing: Listing) -> dict:
    """Resolve a listing's badge: verified property, else fall back to owner."""
    pv = (
        db.query(PropertyVerification)
        .filter(PropertyVerification.listing_id == listing.id)
        .order_by(PropertyVerification.created_at.desc())
        .first()
    )
    if pv and pv.status == "verified":
        return _badge("verified_property")

    owner = listing.owner if getattr(listing, "owner", None) else None
    if owner is not None:
        return user_badge(db, owner)
    return _badge("unverified")
