"""
app/api/v1/endpoints/landlords.py
"""

import re
import os
from typing import List, Optional

import cloudinary
import cloudinary.uploader
from pathlib import Path
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

# Cloudinary config
cloudinary.config(
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.environ.get("CLOUDINARY_API_KEY"),
    api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
    secure     = True
)

VERIFY_DIR = Path("static/uploads/verification")
ALLOWED_DOC_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_DOC_SIZE_MB   = 10
MAX_IMAGE_SIZE_MB = 8
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
PASSWORD_RULE_MSG = (
    "Password must be at least 8 characters and include uppercase, "
    "lowercase, a number, and a special character."
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def require_landlord(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord access required.")
    return current_user


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


async def _upload_to_cloudinary(f: UploadFile) -> str:
    """Upload image to Cloudinary and return the secure URL."""
    mime = (f.content_type or "").lower()
    if mime not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime}.")
    data = await f.read()
    if len(data) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_IMAGE_SIZE_MB}MB limit.")
    try:
        result = cloudinary.uploader.upload(
            data,
            folder="findmynyumba/properties",
            resource_type="image",
            transformation=[{"width": 1200, "crop": "limit", "quality": "auto"}]
        )
        return result["secure_url"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")


async def _save_doc_upload(f: UploadFile, dest_dir: Path, user_id: int, prefix: str = "") -> str:
    """Save verification documents to local disk (these don't need persistence)."""
    import secrets
    mime = (f.content_type or "").lower()
    if mime not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime}.")
    data = await f.read()
    if len(data) > MAX_DOC_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_DOC_SIZE_MB}MB limit.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    rand = secrets.token_hex(4)
    safe_name = f"{user_id}_{prefix}{rand}_{Path(f.filename).name}"
    (dest_dir / safe_name).write_bytes(data)
    return safe_name


# ── Dashboard Stats ───────────────────────────────────────────────────────────
@router.get("/dashboard/stats")
def get_stats(landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    active_listings  = db.query(Listing).filter(Listing.owner_id == landlord.id, Listing.status == "active").count()
    pending_listings = db.query(Listing).filter(Listing.owner_id == landlord.id, Listing.status == "pending").count()
    unread_inquiries = db.query(Message).filter(Message.receiver_id == landlord.id, Message.is_read == False).count()
    return {
        "active_listings":     active_listings,
        "pending_listings":    pending_listings,
        "total_views":         0,
        "unread_inquiries":    unread_inquiries,
        "verification_status": landlord.verification_status or "unverified",
        "rejection_reason":    landlord.verification_rejection_reason or None,
    }


# ── Properties ────────────────────────────────────────────────────────────────
@router.get("/properties")
def get_properties(request: Request, landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    listings = db.query(Listing).filter(Listing.owner_id == landlord.id).order_by(Listing.created_at.desc()).all()
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
    first_image_url = None
    if images:
        for img in images[:10]:
            if not img.filename:
                continue
            url = await _upload_to_cloudinary(img)
            if first_image_url is None:
                first_image_url = url

    listing = Listing(
        title       = title.strip(),
        description = description.strip(),
        price       = price,
        location    = location.strip(),
        image_url   = first_image_url,  # Now a Cloudinary URL
        status      = "pending",
        owner_id    = landlord.id,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return {"status": "success", "message": "Property submitted for review!", "id": listing.id}


@router.put("/properties/{listing_id}")
async def update_property(
    listing_id:  int,
    title:       str = Form(..., min_length=3, max_length=160),
    price:       float = Form(..., ge=0),
    location:    str = Form(..., min_length=2, max_length=200),
    description: str = Form(..., min_length=10, max_length=4000),
    images:      Optional[List[UploadFile]] = File(None),
    landlord:    User    = Depends(require_landlord),
    db:          Session = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.owner_id == landlord.id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Property not found.")

    listing.title       = title.strip()
    listing.description = description.strip()
    listing.price       = price
    listing.location    = location.strip()

    if images:
        for img in images[:10]:
            if not img.filename:
                continue
            url = await _upload_to_cloudinary(img)
            listing.image_url = url
            break  # Use first uploaded image

    db.commit()
    db.refresh(listing)
    return {"status": "success", "message": "Property updated!", "id": listing.id}


@router.get("/properties/{listing_id}")
def get_property(listing_id: int, request: Request, landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.owner_id == landlord.id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Property not found.")
    return {
        "id":          listing.id,
        "title":       listing.title,
        "description": listing.description or "",
        "price":       listing.price,
        "location":    listing.location,
        "status":      listing.status,
        "image_url":   _absolute_image_url(listing.image_url, request),
    }


@router.delete("/properties/{listing_id}")
def delete_property(listing_id: int, landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.owner_id == landlord.id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Property not found.")
    db.delete(listing)
    db.commit()
    return {"status": "success", "message": "Property deleted."}


@router.post("/properties/{listing_id}/boost")
def boost_property(listing_id: int, landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.owner_id == landlord.id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Property not found.")
    listing.is_boosted = not listing.is_boosted
    db.commit()
    return {"status": "success", "boosted": listing.is_boosted}


# ── Inquiries ─────────────────────────────────────────────────────────────────
@router.get("/inquiries")
def get_inquiries(landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    messages = db.query(Message).filter(Message.receiver_id == landlord.id).order_by(Message.created_at.desc()).limit(50).all()
    sender_ids  = {m.sender_id for m in messages}
    listing_ids = {m.property_id for m in messages if m.property_id}
    senders  = {u.id: u for u in db.query(User).filter(User.id.in_(sender_ids)).all()} if sender_ids else {}
    listings = {l.id: l for l in db.query(Listing).filter(Listing.id.in_(listing_ids)).all()} if listing_ids else {}
    result = []
    ids_to_mark = []
    for msg in messages:
        sender  = senders.get(msg.sender_id)
        listing = listings.get(msg.property_id) if msg.property_id else None
        if not msg.is_read:
            ids_to_mark.append(msg.id)
        result.append({
            "id":             msg.id,
            "sender_name":    sender.full_name if sender else "Unknown",
            "sender_email":   sender.email if sender else "",
            "property_title": listing.title if listing else "General Inquiry",
            "message":        msg.content,
            "is_read":        msg.is_read,
            "created_at":     msg.created_at.isoformat() if msg.created_at else None,
        })
    if ids_to_mark:
        db.query(Message).filter(Message.id.in_(ids_to_mark)).update({"is_read": True}, synchronize_session=False)
        db.commit()
    return result


# ── Verification ──────────────────────────────────────────────────────────────
@router.get("/verification")
def get_verification(landlord: User = Depends(require_landlord)):
    return {"verification_status": landlord.verification_status or "unverified", "rejection_reason": landlord.verification_rejection_reason or None}


@router.post("/verify")
async def submit_verification(doc1: UploadFile = File(...), doc2: UploadFile = File(...), landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    if landlord.verification_status == "pending":
        raise HTTPException(status_code=409, detail="A verification request is already pending review.")
    await _save_doc_upload(doc1, VERIFY_DIR, landlord.id, prefix="doc1_")
    await _save_doc_upload(doc2, VERIFY_DIR, landlord.id, prefix="doc2_")
    landlord.verification_status = "pending"
    landlord.verification_rejection_reason = None
    db.commit()
    return {"status": "success", "message": "Verification documents submitted."}


# ── Profile ───────────────────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    full_name:     str           = Field(..., min_length=1, max_length=120)
    phone_number:  Optional[str] = Field(None, max_length=40)
    business_name: Optional[str] = Field(None, max_length=160)


@router.put("/profile")
def update_profile(payload: ProfileUpdate, landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    name = payload.full_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Full name cannot be empty.")
    landlord.full_name = name
    if payload.phone_number is not None:
        landlord.phone_number = payload.phone_number.strip() or None
    if payload.business_name is not None:
        landlord.business_name = payload.business_name.strip() or None
    db.commit()
    return {"status": "success", "message": "Profile updated successfully."}


# ── Change Password ───────────────────────────────────────────────────────────
class PasswordChange(BaseModel):
    current_password: str
    new_password:     str


@router.post("/settings/password")
def change_password(payload: PasswordChange, landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, landlord.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current.")
    if not PASSWORD_RE.match(payload.new_password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MSG)
    landlord.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"status": "success", "message": "Password updated successfully."}
