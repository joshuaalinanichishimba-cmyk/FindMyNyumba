"""
app/core/risk_engine.py

Fraud risk scoring for FindMyNyumba.

DESIGN
------
The score is a 0-100 *trust* score (higher = safer), matching the brief's bands:

    0-30   = High Risk
    31-70  = Medium Risk
    71-100 = Low Risk

We start every user at a neutral floor and ADD points for each verification
signal earned, then SUBTRACT for each negative signal (scam reports, duplicate
listings/images, suspicious chat activity). The result is clamped to 0-100.

This is intentionally transparent and rule-based, not ML: a Trust & Safety
reviewer in Kitwe must be able to look at a number and understand exactly why
it is what it is, and defend a suspension decision. Every contributing factor
is returned in `factors` so the admin UI can show the breakdown.

It reuses the existing scam-signal scanner (app.core.scam_detection) philosophy
but operates at the account level rather than per-message.

USAGE
-----
    from app.core.risk_engine import compute_user_risk, persist_user_risk

    result = compute_user_risk(db, user)          # pure: returns dict, no writes
    persist_user_risk(db, user)                   # computes + upserts RiskScore row

Call persist_user_risk after any event that changes the inputs:
verification approved/rejected, a new fraud report, a listing
created/removed, an account suspended.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.listing import Listing
from app.models.listing_media import ListingMedia
from app.models.trust_models import (
    FraudReport, RiskScore, Verification, VerificationDocument,
)

# â”€â”€ Tunable weights (one place to change policy) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BASE_SCORE = 40            # neutral, unverified starting point

W_PHONE_VERIFIED     = 10
W_EMAIL_VERIFIED     = 10
W_NRC_VERIFIED       = 20   # NRC front+back+selfie reviewed & approved
W_PROPERTY_VERIFIED  = 20   # at least one verified property

# Negatives (subtracted)
W_PER_SCAM_REPORT       = 15   # each substantiated/open scam-category report
W_PER_DUPLICATE_LISTING = 10   # reused photos across the user's own listings
W_SUSPENDED             = 60   # an inactive/suspended account is high-risk

BANDS = [
    (71, "low"),     # 71-100
    (31, "medium"),  # 31-70
    (0,  "high"),    # 0-30
]

SCAM_CATEGORIES = {
    "scam", "fake_landlord", "viewing_fee_request", "agent_fee_scam",
    "fake_photos", "wrong_location",
}


def _band(score: int) -> str:
    for threshold, name in BANDS:
        if score >= threshold:
            return name
    return "high"


def compute_user_risk(db: Session, user: User) -> dict:
    """
    Pure computation. Returns {score, band, factors:[...]} without writing.
    `factors` is a list of human-readable contributions for the admin UI.
    """
    factors: list[dict] = []
    score = BASE_SCORE
    factors.append({"label": "Base score", "delta": BASE_SCORE})

    # â”€â”€ Positive signals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Phone: a recorded phone number AND the latest verification marks it checked.
    latest_v: Optional[Verification] = (
        db.query(Verification)
        .filter(Verification.user_id == user.id)
        .order_by(Verification.created_at.desc())
        .first()
    )

    phone_ok = bool(getattr(user, "phone_number", None)) and bool(
        latest_v and latest_v.phone_verified
    )
    email_ok = bool(getattr(user, "is_verified", False)) or bool(
        latest_v and latest_v.email_verified
    )
    nrc_ok = bool(
        latest_v and latest_v.status == "approved"
        and latest_v.nrc_front_uploaded and latest_v.nrc_back_uploaded
        and latest_v.selfie_uploaded
    )

    if phone_ok:
        score += W_PHONE_VERIFIED
        factors.append({"label": "Phone verified", "delta": W_PHONE_VERIFIED})
    if email_ok:
        score += W_EMAIL_VERIFIED
        factors.append({"label": "Email verified", "delta": W_EMAIL_VERIFIED})
    if nrc_ok:
        score += W_NRC_VERIFIED
        factors.append({"label": "NRC + selfie verified", "delta": W_NRC_VERIFIED})

    # Property verified: any listing owned by this user that has been verified.
    from app.models.trust_models import PropertyVerification
    has_verified_property = (
        db.query(PropertyVerification)
        .join(Listing, Listing.id == PropertyVerification.listing_id)
        .filter(
            Listing.owner_id == user.id,
            PropertyVerification.status == "verified",
        )
        .first()
        is not None
    )
    if has_verified_property:
        score += W_PROPERTY_VERIFIED
        factors.append({"label": "Verified property", "delta": W_PROPERTY_VERIFIED})

    # â”€â”€ Negative signals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    scam_reports = (
        db.query(func.count(FraudReport.id))
        .filter(
            FraudReport.reported_user_id == user.id,
            FraudReport.category.in_(SCAM_CATEGORIES),
            FraudReport.status != "resolved",   # open/active reports weigh in
        )
        .scalar()
    ) or 0
    # Also count reports against this user's listings.
    listing_reports = (
        db.query(func.count(FraudReport.id))
        .join(Listing, Listing.id == FraudReport.listing_id)
        .filter(
            Listing.owner_id == user.id,
            FraudReport.category.in_(SCAM_CATEGORIES),
            FraudReport.status != "resolved",
        )
        .scalar()
    ) or 0
    total_reports = scam_reports + listing_reports
    if total_reports:
        delta = -W_PER_SCAM_REPORT * total_reports
        score += delta
        factors.append({"label": f"{total_reports} open scam report(s)", "delta": delta})

    # Duplicate listings: same perceptual image hash reused across this owner's
    # listings is a strong fake-listing signal.
    dup = _duplicate_listing_count(db, user.id)
    if dup:
        delta = -W_PER_DUPLICATE_LISTING * dup
        score += delta
        factors.append({"label": f"{dup} duplicate-image listing(s)", "delta": delta})

    if not getattr(user, "is_active", True):
        score += -W_SUSPENDED
        factors.append({"label": "Account suspended", "delta": -W_SUSPENDED})

    score = max(0, min(100, score))
    return {"score": score, "band": _band(score), "factors": factors}


def _duplicate_listing_count(db: Session, owner_id: int) -> int:
    """
    Count how many of an owner's verification/listing images share a phash with
    another distinct image. Reused photos are the classic fake-listing tell.
    We look at VerificationDocument.phash here (listing media phashes can be
    added the same way once stored). Returns the number of colliding groups.
    """
    rows = (
        db.query(VerificationDocument.phash)
        .filter(
            VerificationDocument.user_id == owner_id,
            VerificationDocument.phash.isnot(None),
        )
        .all()
    )
    hashes = [r[0] for r in rows if r[0]]
    if not hashes:
        return 0
    # How many of this owner's hashes also appear on a DIFFERENT user?
    collisions = 0
    for h in set(hashes):
        other = (
            db.query(func.count(VerificationDocument.id))
            .filter(
                VerificationDocument.phash == h,
                VerificationDocument.user_id != owner_id,
            )
            .scalar()
        ) or 0
        if other:
            collisions += 1

    # Listing-photo reuse: does any of THIS owner's listing photos share a
    # phash with a listing photo owned by a DIFFERENT user? That cross-owner
    # match is the classic stolen-photo scam signal.
    media_rows = (
        db.query(ListingMedia.image_hash)
        .join(Listing, Listing.id == ListingMedia.listing_id)
        .filter(
            Listing.owner_id == owner_id,
            ListingMedia.image_hash.isnot(None),
        )
        .all()
    )
    media_hashes = {r[0] for r in media_rows if r[0]}
    for h in media_hashes:
        other_owner = (
            db.query(func.count(ListingMedia.id))
            .join(Listing, Listing.id == ListingMedia.listing_id)
            .filter(
                ListingMedia.image_hash == h,
                Listing.owner_id != owner_id,
            )
            .scalar()
        ) or 0
        if other_owner:
            collisions += 1

    return collisions


def persist_user_risk(db: Session, user: User) -> RiskScore:
    """Compute and upsert the user's RiskScore row. Returns the row."""
    result = compute_user_risk(db, user)
    row = (
        db.query(RiskScore)
        .filter(RiskScore.user_id == user.id, RiskScore.listing_id.is_(None))
        .first()
    )
    if row is None:
        row = RiskScore(user_id=user.id)
        db.add(row)
    row.score = result["score"]
    row.band = result["band"]
    row.factors = json.dumps(result["factors"])
    db.commit()
    db.refresh(row)
    return row
