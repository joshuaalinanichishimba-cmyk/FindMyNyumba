"""app/api/v1/endpoints/students.py - Student dashboard endpoints.

All endpoints require student role. SavedListing model ensures
persistent saved listings across sessions and server restarts.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.listing import Listing
from app.models.message import Message
from app.models.user import User
from app.models.saved_listing import SavedListing
from app.models.viewing_request import ViewingRequest, ViewingStatus
from app.models.student_review import StudentReview

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


import os
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True,
)

_ALLOWED_VERIFY_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


async def _upload_verify_doc(f: UploadFile, user_id: int, label: str) -> str:
    """Upload a student verification document to Cloudinary; return secure URL."""
    mime = (f.content_type or "").lower()
    if mime not in _ALLOWED_VERIFY_TYPES:
        raise HTTPException(status_code=400, detail="Document must be a JPG, PNG, WEBP, or PDF.")
    data = await f.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Document must be under 10MB.")
    resource_type = "raw" if mime == "application/pdf" else "image"
    try:
        result = cloudinary.uploader.upload(
            data,
            folder="findmynyumba/verification",
            resource_type=resource_type,
            public_id=f"student_{user_id}_{label}",
            overwrite=True,
        )
        return result.get("secure_url") or result.get("url")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Document upload failed: {e}")


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


# ── Student verification (Student ID + selfie) ──────────────────────────────
@router.post("/verify")
async def submit_student_verification(
    doc1: UploadFile = File(...),   # Student ID card
    doc2: UploadFile = File(...),   # Selfie holding the ID
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Submit student verification documents (Student ID + selfie) for review."""
    if student.verification_status == "pending":
        raise HTTPException(
            status_code=409,
            detail="A verification request is already pending review.",
        )
    student.verification_doc1_url = await _upload_verify_doc(doc1, student.id, "doc1")
    student.verification_doc2_url = await _upload_verify_doc(doc2, student.id, "doc2")
    student.verification_status = "pending"
    student.verification_rejection_reason = None
    db.commit()
    return {"status": "success", "message": "Verification documents submitted for review."}


@router.get("/verification")
def get_student_verification(student: User = Depends(require_student)):
    """Return the student's current verification status."""
    return {
        "verification_status": student.verification_status or "unverified",
        "rejection_reason": student.verification_rejection_reason or None,
    }


# -- Landlord -> Student reviews (two-way reputation) -------------------------
# A landlord may review a student only after a COMPLETED viewing with them.
# Completion required the landlord to verify the student's code in person, so
# every student review traces back to a real, verified visit.
class StudentReviewCreate(BaseModel):
    rating: int
    comment: str
    viewing_id: Optional[int] = None


@router.post("/{student_id}/reviews", status_code=status.HTTP_201_CREATED)
def post_student_review(
    student_id: int,
    review: StudentReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("landlord", "student_host"):
        raise HTTPException(status_code=403, detail="Only hosts can review students.")
    if current_user.id == student_id:
        raise HTTPException(status_code=400, detail="You cannot review yourself.")
    if not (1 <= review.rating <= 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5.")

    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    # GATE: this landlord must have a completed viewing with this student.
    completed = (
        db.query(ViewingRequest)
          .filter(
              ViewingRequest.landlord_id == current_user.id,
              ViewingRequest.student_id == student_id,
              ViewingRequest.status == ViewingStatus.COMPLETED.value,
          )
          .first()
    )
    if not completed:
        raise HTTPException(
            status_code=403,
            detail="You can only review a student after completing a viewing with them.",
        )

    # One review per completed viewing (if viewing_id given), else one per landlord-student pair.
    dup_q = db.query(StudentReview).filter(
        StudentReview.landlord_id == current_user.id,
        StudentReview.student_id == student_id,
    )
    if review.viewing_id is not None:
        dup_q = dup_q.filter(StudentReview.viewing_id == review.viewing_id)
    if dup_q.first():
        raise HTTPException(status_code=409, detail="You have already reviewed this student for this viewing.")

    row = StudentReview(
        student_id=student_id,
        landlord_id=current_user.id,
        viewing_id=review.viewing_id or (completed.id if completed else None),
        landlord_name=current_user.full_name,
        rating=review.rating,
        comment=(review.comment or "").strip(),
        status="pending",
    )
    db.add(row)
    db.commit()
    return {"status": "submitted", "message": "Thank you! Your review will appear after approval."}


@router.get("/{student_id}/reviews")
def list_student_reviews(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(StudentReview)
          .filter(StudentReview.student_id == student_id, StudentReview.status == "approved")
          .order_by(StudentReview.created_at.desc())
          .all()
    )
    avg = round(sum(r.rating for r in rows) / len(rows), 1) if rows else None
    return {
        "count": len(rows),
        "average": avg,
        "reviews": [
            {
                "id": r.id,
                "rating": r.rating,
                "comment": r.comment,
                "landlord_name": r.landlord_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
