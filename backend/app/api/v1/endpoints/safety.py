"""
Safety / Fraud Center endpoints.

Public:
  GET  /safety/verify-landlord?query=...   Look up a phone / account / email and
                                           report whether it belongs to a verified
                                           provider, is unregistered, or is blacklisted.

Admin:
  GET    /admin/trust/blacklist            List active blacklist entries.
  POST   /admin/trust/blacklist            Add an entry (auto-flags matching listings).
  DELETE /admin/trust/blacklist/{id}       Revoke an entry.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_admin
from app.models.blacklist import Blacklist
from app.models.user import User
from app.models.listing import Listing

router = APIRouter()

VALID_ENTITY_TYPES = {"phone", "account", "email"}


def _normalise(value: str) -> str:
    """Lowercase + strip spaces/dashes so lookups are forgiving."""
    v = (value or "").strip().lower()
    return re.sub(r"[\s\-()]", "", v)


# ────────────────────────── PUBLIC LOOKUP ──────────────────────────
@router.get("/safety/verify-landlord")
def verify_landlord(query: str = Query(..., min_length=3, max_length=120),
                    db: Session = Depends(get_db)):
    q = _normalise(query)
    if not q:
        raise HTTPException(status_code=400, detail="Enter a phone number, account, or email to check.")

    # 1. Blacklisted? (highest priority warning)
    bl = (
        db.query(Blacklist)
        .filter(Blacklist.is_active == True, Blacklist.value == q)  # noqa: E712
        .first()
    )
    if bl:
        return {
            "state": "blacklisted",
            "message": "This contact has been blacklisted on FindMyNyumba for fraudulent activity. Do not send any money. Report any interaction to us immediately.",
        }

    # 2. Matches a verified provider?
    #    Match phone or email against users; consider verified if their status is approved/verified.
    user = (
        db.query(User)
        .filter(or_(User.phone_number == query.strip(), User.phone_number == q, User.email == query.strip().lower()))
        .first()
    )
    if user:
        verified = (
            getattr(user, "verification_status", None) in ("approved", "verified")
            or getattr(user, "is_verified", False) is True
        )
        if verified:
            return {
                "state": "verified",
                "name": getattr(user, "full_name", None) or "Verified provider",
                "message": "This contact belongs to a verified provider on FindMyNyumba.",
            }
        return {
            "state": "unverified",
            "message": "This contact is registered but not yet verified. Take extra care and never pay before inspecting the property in person.",
        }

    # 3. Not found anywhere
    return {
        "state": "unverified",
        "message": "We could not find this contact as a verified provider on FindMyNyumba. Proceed with caution and never pay before inspecting the property in person.",
    }


# ────────────────────────── ADMIN BLACKLIST ──────────────────────────
def _bl_dict(b: Blacklist) -> dict:
    return {
        "id": b.id,
        "entity_type": b.entity_type,
        "value": b.value,
        "reason": b.reason,
        "admin_note": b.admin_note,
        "is_active": b.is_active,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


@router.get("/admin/trust/blacklist")
def list_blacklist(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(Blacklist)
        .filter(Blacklist.is_active == True)  # noqa: E712
        .order_by(Blacklist.created_at.desc())
        .all()
    )
    return {"count": len(rows), "entries": [_bl_dict(b) for b in rows]}


class BlacklistCreate(BaseModel):
    entity_type: str = Field(..., min_length=3, max_length=20)
    value:       str = Field(..., min_length=3, max_length=200)
    reason:      Optional[str] = Field(None, max_length=200)
    admin_note:  Optional[str] = None


@router.post("/admin/trust/blacklist", status_code=201)
def add_blacklist(payload: BlacklistCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    et = payload.entity_type.strip().lower()
    if et not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail="Entity type must be phone, account, or email.")

    value = _normalise(payload.value)
    existing = db.query(Blacklist).filter(Blacklist.is_active == True, Blacklist.value == value).first()  # noqa: E712
    if existing:
        raise HTTPException(status_code=409, detail="That value is already blacklisted.")

    entry = Blacklist(
        entity_type=et,
        value=value,
        reason=(payload.reason or "").strip() or None,
        admin_note=(payload.admin_note or "").strip() or None,
        is_active=True,
        created_by=admin.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Auto-flag active listings whose owner matches this phone/email.
    flagged = 0
    try:
        if et in ("phone", "email"):
            col = User.phone_number if et == "phone" else User.email
            owners = db.query(User.id).filter(col.isnot(None)).all()
            match_ids = [uid for (uid,) in owners
                         if _normalise(getattr(db.query(User).get(uid), "phone_number" if et == "phone" else "email") or "") == value]
            if match_ids:
                listings = db.query(Listing).filter(Listing.owner_id.in_(match_ids), Listing.status == "active").all()
                for l in listings:
                    l.status = "flagged_pending_review"
                    flagged += 1
                db.commit()
    except Exception:
        db.rollback()

    return {"status": "success", "entry": _bl_dict(entry), "listings_flagged": flagged}


@router.delete("/admin/trust/blacklist/{entry_id}")
def revoke_blacklist(entry_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    entry = db.query(Blacklist).filter(Blacklist.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Blacklist entry not found.")
    entry.is_active = False
    db.commit()
    return {"status": "success", "message": "Blacklist entry revoked."}
