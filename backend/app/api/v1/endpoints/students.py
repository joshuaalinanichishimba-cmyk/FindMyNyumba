"""
app/api/v1/endpoints/students.py

Student dashboard endpoints. The original file shipped under this name was
a copy of messages.py, which meant every call from dashboard-student.html
to /students/* returned 404. This module rebuilds the surface the frontend
actually uses:

  GET  /students/dashboard/overview      → cards + recent listings + recommendations
  GET  /students/saved                   → saved rooms (empty until SavedListing model exists)
  POST /students/saved/{listing_id}      → save a listing (acknowledge until model exists)
  DELETE /students/saved/{listing_id}    → unsave a listing
  PUT  /students/profile                 → update profile
  POST /students/settings/password       → change password

Notes:
  * "Saved rooms" needs a junction table (SavedListing) to persist across
    sessions. Until that model is added, the GET endpoint returns an empty
    list and POST/DELETE return success without persisting. The UI already
    renders the empty state correctly, so the dashboard works end-to-end.
  * Password regex is kept identical to auth.py so a password that registers
    successfully can also be changed later (the original landlord/host
    endpoints used a stricter {8,12} bound — fixed there too).
"""

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.listing import Listing
from app.models.message import Message
from app.models.user import User

router = APIRouter(prefix="/students", tags=["Students"])


# Single source of truth for password complexity rules across the app.
# Matches auth.py: at least 8 chars, lower + upper + digit + symbol.
PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
PASSWORD_RULE_MSG = (
    "Password must be at least 8 characters and include uppercase, "
    "lowercase, a number, and a special character."
)


# ── Role guard ────────────────────────────────────────────────────────────────
def require_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required.",
        )
    return current_user


# ── Helpers ───────────────────────────────────────────────────────────────────
def _resolve_image(raw: Optional[str]) -> Optional[str]:
    """
    Listing.image_url is stored as a bare filename (e.g. "12_room.jpg").
    Return a path relative to the API host so the frontend doesn't have to
    guess. Frontend's resolveImageUrl() prepends the host as needed.
    """
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        return raw
    return f"/static/uploads/properties/{raw}"


def _listing_card(l: Listing) -> dict:
    """Compact representation used in dashboard cards/grids."""
    return {
        "id":         l.id,
        "title":      l.title,
        "price":      l.price,
        "location":   l.location,
        "image_url":  _resolve_image(l.image_url),
        "is_boosted": l.is_boosted,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


# ── GET /students/dashboard/overview ──────────────────────────────────────────
@router.get("/dashboard/overview")
def get_overview(
    student: User = Depends(require_student),
    db:      Session = Depends(get_db),
):
    """
    Powers the student overview tab. Frontend reads:
      - data.stats.saved_count
      - data.stats.unread_messages_count
      - data.recent_properties (array of compact listing cards)
    """
    unread_messages_count = (
        db.query(Message)
          .filter(Message.receiver_id == student.id, Message.is_read == False)
          .count()
    )

    # TODO: once SavedListing model exists, count saved rows for this user.
    saved_count = 0

    recent_properties = (
        db.query(Listing)
          .filter(Listing.status == "active")
          .order_by(Listing.is_boosted.desc(), Listing.created_at.desc())
          .limit(6)
          .all()
    )

    return {
        "stats": {
            "saved_count":           saved_count,
            "unread_messages_count": unread_messages_count,
        },
        "recent_properties": [_listing_card(l) for l in recent_properties],
    }


# ── Saved rooms (stubbed until SavedListing model lands) ──────────────────────
@router.get("/saved")
def list_saved(
    student: User = Depends(require_student),
    db:      Session = Depends(get_db),
):
    """
    Returns the student's saved listings. Currently returns an empty list —
    persistence will come once the SavedListing junction table is added.
    The dashboard renders the empty state correctly, so this is non-breaking.
    """
    return []


@router.post("/saved/{listing_id}", status_code=201)
def save_listing(
    listing_id: int,
    student:    User    = Depends(require_student),
    db:         Session = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    # TODO: insert into saved_listings(user_id, listing_id, created_at)
    return {"status": "success", "message": "Saved."}


@router.delete("/saved/{listing_id}")
def unsave_listing(
    listing_id: int,
    student:    User    = Depends(require_student),
    db:         Session = Depends(get_db),
):
    # TODO: delete from saved_listings
    return {"status": "success", "message": "Removed."}


# ── PUT /students/profile ─────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    full_name: str
    phone:     Optional[str] = None


@router.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    student: User    = Depends(require_student),
    db:      Session = Depends(get_db),
):
    if not payload.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name cannot be empty.")

    student.full_name = payload.full_name.strip()
    if payload.phone is not None:
        # Allow clearing the phone with an empty string
        student.phone_number = payload.phone.strip() or None
    db.commit()

    return {
        "status":  "success",
        "message": "Profile updated successfully.",
        "user": {
            "id":        student.id,
            "full_name": student.full_name,
            "email":     student.email,
            "phone":     student.phone_number,
        },
    }


# ── POST /students/settings/password ──────────────────────────────────────────
class PasswordChange(BaseModel):
    current_password: str
    new_password:     str


@router.post("/settings/password")
def change_password(
    payload: PasswordChange,
    student: User    = Depends(require_student),
    db:      Session = Depends(get_db),
):
    if not verify_password(payload.current_password, student.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from your current password.",
        )

    if not PASSWORD_RE.match(payload.new_password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MSG)

    student.hashed_password = get_password_hash(payload.new_password)
    # Reset any pending password-reset token so it can't be reused after a
    # voluntary password change.
    student.reset_token_hash = None
    student.reset_token_used = True
    db.commit()

    return {"status": "success", "message": "Password updated successfully."}
