"""
app/api/v1/endpoints/student_hosts.py

FIXES:
- dashboard/stats: returns fields frontend actually reads:
    active_listings, pending_listings, total_views,
    unread_inquiries, verification_status, rejection_reason
- GET /properties: returns bare list (no wrapper) — frontend uses .length directly
- GET /verification: returns { verification_status, rejection_reason } — no wrapper
- POST /verify: endpoint added (was missing — caused 404 in logs)
- DELETE /properties/{id}: endpoint added for delete button in My Listings
- PUT /profile: endpoint added for Profile & Settings form
- POST /settings/password: endpoint added for Change Password form
- Role guard: all endpoints require student_host role
- All responses aligned to what the frontend JS actually reads
"""

import shutil
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.listing import Listing
from app.models.message import Message
from app.models.user import User

router = APIRouter(prefix="/student-host", tags=["Student Host"])

UPLOAD_DIR = Path("static/uploads/properties")
VERIFY_DIR = Path("static/uploads/verification")


# ── Role guard ────────────────────────────────────────────────────────────────
def require_student_host(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "student_host":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student host access required.",
        )
    return current_user


# ── Dashboard Stats ───────────────────────────────────────────────────────────
@router.get("/dashboard/stats")
def get_host_stats(
    host: User = Depends(require_student_host),
    db: Session = Depends(get_db),
):
    """
    Returns exactly the fields the frontend reads:
      active_listings, pending_listings, total_views,
      unread_inquiries, verification_status, rejection_reason
    """
    active_listings  = db.query(Listing).filter(
        Listing.owner_id == host.id,
        Listing.status   == "active",
    ).count()

    pending_listings = db.query(Listing).filter(
        Listing.owner_id == host.id,
        Listing.status   == "pending",
    ).count()

    # Unread messages addressed to this host
    unread_inquiries = db.query(Message).filter(
        Message.receiver_id == host.id,
        Message.is_read     == False,
    ).count()

    # Total views: placeholder — wire to a ListingView model when available
    total_views = 0

    return {
        "active_listings":     active_listings,
        "pending_listings":    pending_listings,
        "total_views":         total_views,
        "unread_inquiries":    unread_inquiries,
        "verification_status": host.verification_status or "unverified",
        "rejection_reason":    host.verification_rejection_reason or None,
    }


# ── Listings ──────────────────────────────────────────────────────────────────
@router.get("/properties")
@router.get("/listings")
def get_host_listings(
    host: User = Depends(require_student_host),
    db: Session = Depends(get_db),
):
    """Returns a bare list — frontend uses .length and .map() directly."""
    listings = (
        db.query(Listing)
        .filter(Listing.owner_id == host.id)
        .order_by(Listing.created_at.desc())
        .all()
    )
    return [
        {
            "id":         l.id,
            "title":      l.title,
            "price":      l.price,
            "location":   l.location,
            "status":     l.status,
            "is_boosted": l.is_boosted,
            "image_url":  f"/static/uploads/properties/{l.image_url}" if l.image_url else None,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in listings
    ]


@router.post("/properties")
@router.post("/listings")
async def create_host_listing(
    title:               str            = Form(...),
    price:               float          = Form(...),
    location:            str            = Form(...),
    description:         str            = Form(...),
    nearest_institution: Optional[str]  = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    host: User         = Depends(require_student_host),
    db: Session        = Depends(get_db),
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    first_image_name = None
    if images:
        for img in images:
            if not img.filename:
                continue
            safe_name = f"{host.id}_{img.filename.replace(' ', '_')}"
            dest = UPLOAD_DIR / safe_name
            with open(dest, "wb") as buf:
                shutil.copyfileobj(img.file, buf)
            if first_image_name is None:
                first_image_name = safe_name

    listing = Listing(
        title       = title.strip(),
        description = description.strip(),
        price       = price,
        location    = location.strip(),
        image_url   = first_image_name,
        status      = "pending",   # always pending — awaits admin approval
        owner_id    = host.id,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return {"message": "Bedspace submitted for review!", "id": listing.id}


@router.delete("/properties/{listing_id}")
def delete_host_listing(
    listing_id: int,
    host: User  = Depends(require_student_host),
    db: Session = Depends(get_db),
):
    listing = db.query(Listing).filter(
        Listing.id       == listing_id,
        Listing.owner_id == host.id,
    ).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    db.delete(listing)
    db.commit()
    return {"message": "Listing deleted."}


# ── Verification ──────────────────────────────────────────────────────────────
@router.get("/verification")
def get_host_verification(host: User = Depends(require_student_host)):
    """
    Returns { verification_status, rejection_reason } — no wrapper.
    Frontend destructures these two keys directly.
    """
    return {
        "verification_status": host.verification_status or "unverified",
        "rejection_reason":    host.verification_rejection_reason or None,
    }


@router.post("/verify")
async def submit_verification(
    doc1: UploadFile   = File(...),
    doc2: UploadFile   = File(...),
    host: User         = Depends(require_student_host),
    db: Session        = Depends(get_db),
):
    """
    Accepts two uploaded documents and marks verification as pending.
    This endpoint was missing — caused 404 in logs.
    """
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)

    for doc, label in [(doc1, "doc1"), (doc2, "doc2")]:
        if not doc.filename:
            raise HTTPException(status_code=400, detail=f"{label} is required.")
        safe_name = f"{host.id}_{label}_{doc.filename.replace(' ', '_')}"
        with open(VERIFY_DIR / safe_name, "wb") as buf:
            shutil.copyfileobj(doc.file, buf)

    host.verification_status = "pending"
    db.commit()
    return {"message": "Verification documents submitted. You will be notified once reviewed."}


# ── Profile ───────────────────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    full_name: str
    phone:     Optional[str] = None


@router.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    host: User  = Depends(require_student_host),
    db: Session = Depends(get_db),
):
    if not payload.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name cannot be empty.")
    host.full_name    = payload.full_name.strip()
    host.phone_number = payload.phone or host.phone_number
    db.commit()
    return {"message": "Profile updated successfully."}


# ── Change Password ───────────────────────────────────────────────────────────
class PasswordChange(BaseModel):
    current_password: str
    new_password:     str


@router.post("/settings/password")
def change_password(
    payload: PasswordChange,
    host: User  = Depends(require_student_host),
    db: Session = Depends(get_db),
):
    import re
    if not verify_password(payload.current_password, host.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    PWD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,12}$")
    if not PWD_RE.match(payload.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8-12 characters with uppercase, lowercase, number, and special character.",
        )
    host.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully."}
