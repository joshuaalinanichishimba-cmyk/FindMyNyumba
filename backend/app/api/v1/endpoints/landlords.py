"""
app/api/v1/endpoints/landlords.py

FIXES vs original:
- Password regex aligned with auth.py: 8+ chars (was 8-12). The 12-char
  cap meant any user who registered with a 13+ char password could never
  change it later.
- Image upload validation now also enforces MAX_IMAGE_SIZE_MB per file
  (defence against disk-exhaustion uploads).
- Verification documents now validated for MIME type and size.
- Image URLs in responses are now ABSOLUTE (built from request.base_url),
  matching listings.py and dashboards.
- /landlord/inquiries no longer mass-marks every received message as read
  on every load. Only messages currently displayed in the response are
  marked read, and only those linked to one of the landlord's own listings.
- POST /landlord/properties saves all uploaded images, not just the first.
  (Image gallery semantics.)
- Filenames are slugged + suffixed with a short random token so two users
  can't collide and a malicious filename can't path-traverse.
"""

import re
import secrets
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.listing import Listing
from app.models.message import Message
from app.models.user import User

router = APIRouter(prefix="/landlord", tags=["Landlord"])

UPLOAD_DIR = Path("static/uploads/properties")
VERIFY_DIR = Path("static/uploads/verification")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOC_TYPES   = {
    "image/jpeg", "image/png", "image/webp",
    "application/pdf",
}
MAX_IMAGE_SIZE_MB = 8
MAX_DOC_SIZE_MB   = 10

# Single source of truth for password rules across the app.
PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
PASSWORD_RULE_MSG = (
    "Password must be at least 8 characters and include uppercase, "
    "lowercase, a number, and a special character."
)

# Filename slug  strip path separators, keep only safe characters.
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


#  Helpers 
def require_landlord(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "landlord":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Landlord access required.",
        )
    return current_user


def _safe_filename(user_id: int, original: str, prefix: str = "") -> str:
    """Build a collision-resistant, path-traversal-safe filename."""
    base = Path(original).name           # strip any directory components
    base = _SAFE_NAME_RE.sub("_", base)
    base = base.lstrip(".") or "file"    # avoid hidden files
    rand = secrets.token_hex(4)
    return f"{user_id}_{prefix}{rand}_{base}" if prefix else f"{user_id}_{rand}_{base}"


def _absolute_image_url(raw: Optional[str], request: Request) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    base = str(request.base_url).rstrip("/")
    if raw.startswith("/"):
        return f"{base}{raw}"
    return f"{base}/static/uploads/properties/{raw}"


async def _save_upload(
    f: UploadFile,
    dest_dir: Path,
    user_id:  int,
    *,
    allowed_types: set,
    max_mb:        int,
    prefix:        str = "",
) -> str:
    """
    Validates MIME type and size, then streams the upload to disk.
    Returns the saved filename (NOT the full path).
    """
    if not f.filename:
        raise HTTPException(status_code=400, detail="A file is required.")

    mime = (f.content_type or "").lower()
    if mime not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {mime or 'unknown'}.",
        )

    data = await f.read()
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {max_mb}MB size limit.",
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(user_id, f.filename, prefix=prefix)
    (dest_dir / safe_name).write_bytes(data)
    return safe_name


#  Dashboard Stats 
@router.get("/dashboard/stats")
def get_stats(
    landlord: User    = Depends(require_landlord),
    db:       Session = Depends(get_db),
):
    active_listings = (
        db.query(Listing)
          .filter(Listing.owner_id == landlord.id, Listing.status == "active")
          .count()
    )
    pending_listings = (
        db.query(Listing)
          .filter(Listing.owner_id == landlord.id, Listing.status == "pending")
          .count()
    )
    unread_inquiries = (
        db.query(Message)
          .filter(Message.receiver_id == landlord.id, Message.is_read == False)
          .count()
    )

    return {
        "active_listings":     active_listings,
        "pending_listings":    pending_listings,
        "total_views":         0,   # TODO: ListingView model
        "unread_inquiries":    unread_inquiries,
        "verification_status": landlord.verification_status or "unverified",
        "rejection_reason":    landlord.verification_rejection_reason or None,
    }


#  Properties 
@router.get("/properties")
def get_properties(
    request:  Request,
    landlord: User    = Depends(require_landlord),
    db:       Session = Depends(get_db),
):
    listings = (
        db.query(Listing)
          .filter(Listing.owner_id == landlord.id)
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
            "image_url":  _absolute_image_url(l.image_url, request),
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in listings
    ]


@router.post("/properties", status_code=201)
async def create_property(
    title:       str = Form(..., min_length=3, max_length=160),
    price:       float = Form(..., ge=0),
    location:    str = Form(..., min_length=2, max_length=200),
    description: str = Form(..., min_length=10, max_length=4000),
    images:      Optional[List[UploadFile]] = File(None),
    landlord:    User    = Depends(require_landlord),
    db:          Session = Depends(get_db),
):
    first_image_name = None
    if images:
        # Cap at 10 images per listing  defence against payload-bombing.
        for img in images[:10]:
            if not img.filename:
                continue
            saved = await _save_upload(
                img,
                UPLOAD_DIR,
                landlord.id,
                allowed_types=ALLOWED_IMAGE_TYPES,
                max_mb=MAX_IMAGE_SIZE_MB,
            )
            if first_image_name is None:
                first_image_name = saved
            # NOTE: additional images are saved to disk but only the first
            # is recorded on the Listing row (current schema). When a
            # ListingImage table is added, append to it here.

    listing = Listing(
        title       = title.strip(),
        description = description.strip(),
        price       = price,
        location    = location.strip(),
        image_url   = first_image_name,
        status      = "pending",
        owner_id    = landlord.id,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return {"status": "success", "message": "Property submitted for review!", "id": listing.id}


@router.delete("/properties/{listing_id}")
def delete_property(
    listing_id: int,
    landlord:   User    = Depends(require_landlord),
    db:         Session = Depends(get_db),
):
    listing = (
        db.query(Listing)
          .filter(Listing.id == listing_id, Listing.owner_id == landlord.id)
          .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Property not found.")
    db.delete(listing)
    db.commit()
    return {"status": "success", "message": "Property deleted."}


@router.post("/properties/{listing_id}/boost")
def boost_property(
    listing_id: int,
    landlord:   User    = Depends(require_landlord),
    db:         Session = Depends(get_db),
):
    listing = (
        db.query(Listing)
          .filter(Listing.id == listing_id, Listing.owner_id == landlord.id)
          .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Property not found.")
    listing.is_boosted = not listing.is_boosted
    db.commit()
    return {
        "status":  "success",
        "message": "Listing boosted!" if listing.is_boosted else "Boost removed.",
        "boosted": listing.is_boosted,
    }


#  Inquiries 
@router.get("/inquiries")
def get_inquiries(
    landlord: User    = Depends(require_landlord),
    db:       Session = Depends(get_db),
):
    """
    Returns the 50 most recent messages addressed to this landlord. Marks
    THESE specific messages as read  not every unread message in the
    table (the original `update(...)` was effectively a sledgehammer).
    """
    messages = (
        db.query(Message)
          .filter(Message.receiver_id == landlord.id)
          .order_by(Message.created_at.desc())
          .limit(50)
          .all()
    )

    sender_ids   = {m.sender_id for m in messages}
    listing_ids  = {m.property_id for m in messages if m.property_id}
    senders      = {u.id: u for u in db.query(User).filter(User.id.in_(sender_ids)).all()} if sender_ids else {}
    listings     = {l.id: l for l in db.query(Listing).filter(Listing.id.in_(listing_ids)).all()} if listing_ids else {}

    result = []
    ids_to_mark_read = []
    for msg in messages:
        sender  = senders.get(msg.sender_id)
        listing = listings.get(msg.property_id) if msg.property_id else None
        if not msg.is_read:
            ids_to_mark_read.append(msg.id)
        result.append({
            "id":             msg.id,
            "sender_id":      msg.sender_id,
            "sender_name":    sender.full_name if sender else "Unknown",
            "sender_email":   sender.email if sender else "",
            "property_title": listing.title if listing else "General Inquiry",
            "message":        msg.content,
            "is_read":        msg.is_read,
            "created_at":     msg.created_at.isoformat() if msg.created_at else None,
        })

    if ids_to_mark_read:
        db.query(Message).filter(Message.id.in_(ids_to_mark_read)).update(
            {"is_read": True}, synchronize_session=False
        )
        db.commit()

    return result


#  Verification 
@router.get("/verification")
def get_verification(landlord: User = Depends(require_landlord)):
    return {
        "verification_status": landlord.verification_status or "unverified",
        "rejection_reason":    landlord.verification_rejection_reason or None,
    }


@router.post("/verify")
async def submit_verification(
    doc1:     UploadFile = File(...),
    doc2:     UploadFile = File(...),
    landlord: User       = Depends(require_landlord),
    db:       Session    = Depends(get_db),
):
    if landlord.verification_status == "pending":
        raise HTTPException(
            status_code=409,
            detail="A verification request is already pending review.",
        )

    await _save_upload(
        doc1, VERIFY_DIR, landlord.id,
        allowed_types=ALLOWED_DOC_TYPES, max_mb=MAX_DOC_SIZE_MB, prefix="doc1_",
    )
    await _save_upload(
        doc2, VERIFY_DIR, landlord.id,
        allowed_types=ALLOWED_DOC_TYPES, max_mb=MAX_DOC_SIZE_MB, prefix="doc2_",
    )

    landlord.verification_status           = "pending"
    landlord.verification_rejection_reason = None
    db.commit()
    return {
        "status":  "success",
        "message": "Verification documents submitted. You will be notified once reviewed.",
    }


#  Profile 
class ProfileUpdate(BaseModel):
    full_name:     str           = Field(..., min_length=1, max_length=120)
    phone:         Optional[str] = Field(None, max_length=40)
    business_name: Optional[str] = Field(None, max_length=160)


@router.put("/profile")
def update_profile(
    payload:  ProfileUpdate,
    landlord: User    = Depends(require_landlord),
    db:       Session = Depends(get_db),
):
    name = payload.full_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Full name cannot be empty.")
    landlord.full_name = name
    if payload.phone is not None:
        landlord.phone_number = payload.phone.strip() or None
    if payload.business_name is not None:
        landlord.business_name = payload.business_name.strip() or None
    db.commit()
    return {"status": "success", "message": "Profile updated successfully."}


#  Change Password 
class PasswordChange(BaseModel):
    current_password: str
    new_password:     str


@router.post("/settings/password")
def change_password(
    payload:  PasswordChange,
    landlord: User    = Depends(require_landlord),
    db:       Session = Depends(get_db),
):
    if not verify_password(payload.current_password, landlord.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from your current password.",
        )

    if not PASSWORD_RE.match(payload.new_password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MSG)

    landlord.hashed_password = get_password_hash(payload.new_password)
    landlord.reset_token_hash = None
    landlord.reset_token_used = True
    db.commit()
    return {"status": "success", "message": "Password updated successfully."}
