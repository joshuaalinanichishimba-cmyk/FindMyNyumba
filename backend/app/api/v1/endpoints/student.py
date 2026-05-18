"""
app/api/v1/endpoints/student.py

FULL IMPLEMENTATION — this file did not exist in the provided files,
but dashboard-student.html calls these endpoints:

  GET  /students/dashboard/overview   — stats + recent listings
  GET  /students/profile              — (unused by frontend, /auth/me used instead)
  PUT  /students/profile              — update name + phone
  POST /students/settings/password    — change password

FIXES (relative to what dashboard-student.html expects):
  - /students/dashboard/overview returns:
      { stats: { saved_count, unread_messages_count }, recent_properties: [...] }
  - PUT /students/profile accepts { full_name, phone }
  - POST /students/settings/password accepts { current_password, new_password }
  - Role guard: only 'student' role is allowed
"""

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.listing import Listing
from app.models.message import Message
from app.models.user import User

router = APIRouter(prefix="/students", tags=["Student"])


# ── Role guard ─────────────────────────────────────────────────────────────────
def require_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required.",
        )
    return current_user


# ── GET /students/dashboard/overview ─────────────────────────────────────────
@router.get("/dashboard/overview")
def get_overview(
    request: Request,
    student: User    = Depends(require_student),
    db: Session      = Depends(get_db),
):
    """
    Returns what dashboard-student.html reads:
      data.stats.saved_count
      data.stats.unread_messages_count
      data.recent_properties   → array of listing objects
    """
    unread_count = db.query(Message).filter(
        Message.receiver_id == student.id,
        Message.is_read     == False,
    ).count()

    # Saved rooms: stored in localStorage on the frontend (no DB model yet).
    # Return 0 until a SavedListing model is added.
    saved_count = 0

    # Recent active listings (newest 6)
    recent = (
        db.query(Listing)
        .filter(Listing.status == "active")
        .order_by(Listing.is_boosted.desc(), Listing.created_at.desc())
        .limit(6)
        .all()
    )

    def resolve_img(raw: Optional[str]) -> Optional[str]:
        """Return an absolute URL the browser can use regardless of deployment."""
        if not raw:
            return None
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        base = str(request.base_url).rstrip("/")
        if raw.startswith("/"):
            return f"{base}{raw}"
        return f"{base}/static/uploads/properties/{raw}"

    return {
        "stats": {
            "saved_count":            saved_count,
            "unread_messages_count":  unread_count,
        },
        "recent_properties": [
            {
                "id":         l.id,
                "title":      l.title,
                "price":      l.price,
                "location":   l.location,
                "image_url":  resolve_img(l.image_url),
                "is_boosted": l.is_boosted,
            }
            for l in recent
        ],
    }


# ── GET /students/saved ───────────────────────────────────────────────────────
@router.get("/saved")
def get_saved(
    student: User = Depends(require_student),
):
    """
    Saved listings are stored client-side in localStorage (no DB model yet).
    This endpoint exists so the frontend fetch doesn't 404. It returns an empty
    list — the dashboard JS layer already merges this with localStorage data.
    When a SavedListing model is added, query it here.
    """
    return []


# ── PUT /students/profile ─────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    full_name: str
    phone:     Optional[str] = None

@router.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    student: User    = Depends(require_student),
    db: Session      = Depends(get_db),
):
    if not payload.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name cannot be empty.")
    student.full_name    = payload.full_name.strip()
    student.phone_number = payload.phone or student.phone_number
    db.commit()
    return {"status": "success", "message": "Profile updated successfully."}


# ── POST /students/settings/password ─────────────────────────────────────────
class PasswordChange(BaseModel):
    current_password: str
    new_password:     str

@router.post("/settings/password")
def change_password(
    payload: PasswordChange,
    student: User    = Depends(require_student),
    db: Session      = Depends(get_db),
):
    if not verify_password(payload.current_password, student.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    PWD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
    if not PWD_RE.match(payload.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters with uppercase, lowercase, number, and special character.",
        )
    student.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"status": "success", "message": "Password updated successfully."}
