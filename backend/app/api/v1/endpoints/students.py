"""app/api/v1/endpoints/students.py - Student dashboard endpoints.

All endpoints require student role. SavedListing model ensures
persistent saved listings across sessions and server restarts.
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
from app.models.saved_listing import SavedListing

router = APIRouter(prefix="/students", tags=["Students"])

PASSWORD_RULE_MSG = (
    "Password must be at least 8 characters with uppercase, lowercase, "
    "number, and special character."
)
PASSWORD_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$"
)


def require_student(current_user: User = Depends(get_current_user)) -> User:
    """Guard: only students can access these endpoints."""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required.",
        )
    return current_user


def _resolve_image(raw: Optional[str]) -> Optional[str]:
    """Resolve image URL: Cloudinary (full URL) or local path."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        return raw
    return f"/static/uploads/properties/{raw}"


def _listing_card(l: Listing) -> dict:
    """Compact listing representation for cards/grids."""
    return {
        "id": l.id,
        "title": l.title,
        "price": l.price,
        "location": l.location,
        "image_url": _resolve_image(l.image_url),
        "is_boosted": l.is_boosted,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


@router.get("/dashboard/overview")
def get_overview(
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Student dashboard overview: stats + recent listings."""
    # Count unread messages
    unread_count = (
        db.query(Message)
        .filter(Message.receiver_id == student.id, Message.is_read == False)
        .count()
    )

    # Count saved listings from SavedListing model
    saved_count = (
        db.query(SavedListing)
        .filter(SavedListing.student_id == student.id)
        .count()
    )

    # Get recent active listings
    recent_props = (
        db.query(Listing)
        .filter(Listing.status == "active")
        .order_by(Listing.is_boosted.desc(), Listing.created_at.desc())
        .limit(6)
        .all()
    )

    return {
        "stats": {
            "saved_count": saved_count,
            "unread_messages_count": unread_count,
        },
        "recent_properties": [_listing_card(l) for l in recent_props],
    }


@router.get("/saved")
def list_saved(
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Get all saved listings for the student."""
    saved = (
        db.query(SavedListing)
        .filter(SavedListing.student_id == student.id)
        .all()
    )
    return [_listing_card(sl.listing) for sl in saved]


@router.post("/saved/{listing_id}", status_code=status.HTTP_201_CREATED)
def save_listing(
    listing_id: int,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Save a listing for the student."""
    # Verify listing exists
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # Check if already saved (unique constraint)
    existing = (
        db.query(SavedListing)
        .filter(
            SavedListing.student_id == student.id,
            SavedListing.listing_id == listing_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Listing already saved.")

    # Create SavedListing record
    saved = SavedListing(student_id=student.id, listing_id=listing_id)
    db.add(saved)
    db.commit()
    db.refresh(saved)

    return {"status": "success", "message": "Listing saved."}


@router.delete("/saved/{listing_id}")
def unsave_listing(
    listing_id: int,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Remove a listing from saved."""
    saved = (
        db.query(SavedListing)
        .filter(
            SavedListing.student_id == student.id,
            SavedListing.listing_id == listing_id,
        )
        .first()
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Saved listing not found.")

    db.delete(saved)
    db.commit()

    return {"status": "success", "message": "Listing removed from saved."}


class ProfileUpdate(BaseModel):
    full_name: str
    phone: Optional[str] = None


@router.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Update student profile (name, phone)."""
    if not payload.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name cannot be empty.")

    student.full_name = payload.full_name.strip()
    if payload.phone is not None:
        student.phone_number = payload.phone.strip() or None

    db.commit()

    return {
        "status": "success",
        "message": "Profile updated successfully.",
        "user": {
            "id": student.id,
            "full_name": student.full_name,
            "email": student.email,
            "phone": student.phone_number,
        },
    }


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/settings/password")
def change_password(
    payload: PasswordChange,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Change student password."""
    # Verify current password
    if not verify_password(payload.current_password, student.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    # New password must be different
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must differ from current password.",
        )

    # Validate new password strength
    if not PASSWORD_RE.match(payload.new_password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MSG)

    # Update password
    student.hashed_password = get_password_hash(payload.new_password)
    student.reset_token_hash = None
    student.reset_token_used = True
    db.commit()

    return {"status": "success", "message": "Password updated successfully."}
