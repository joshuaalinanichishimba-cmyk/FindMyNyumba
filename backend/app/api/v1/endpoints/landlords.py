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
from app.models.listing_media import ListingMedia, MediaType
from app.core import media_validation as mv
from app.core.image_hash import phash_bytes
from app.models.message import Message
from app.models.review import Review
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

# â”€â”€ Verification document upload to Cloudinary (PERSISTENT) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Verification docs were previously saved to local disk, which Render wipes on
# every deploy. This uploads them to Cloudinary instead so they survive.
# NOTE (privacy): these land in a dedicated folder with unguessable URLs. The
# URLs are public-but-unguessable, not truly private. For NRC/selfie data,
# upgrade to Cloudinary "authenticated" delivery (signed URLs) when you do the
# broader data-protection hardening.

async def _upload_doc_to_cloudinary(f: UploadFile, user_id: int, label: str) -> str:
    """Upload a verification document to Cloudinary; return the secure URL."""
    mime = (f.content_type or "").lower()
    if mime not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported document type: {mime}.")
    data = await f.read()
    if len(data) > MAX_DOC_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Document exceeds {MAX_DOC_SIZE_MB}MB limit.")
    # PDFs upload as resource_type "raw"; images as "image".
    resource_type = "raw" if mime == "application/pdf" else "image"
    try:
        result = cloudinary.uploader.upload(
            data,
            folder="findmynyumba/verification",
            resource_type=resource_type,
            public_id=f"user_{user_id}_{label}",
            overwrite=True,
        )
        return result["secure_url"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Document upload failed: {e}")


PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
PASSWORD_RULE_MSG = (
    "Password must be at least 8 characters and include uppercase, "
    "lowercase, a number, and a special character."
)


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def require_landlord(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord access required.")
    return current_user


def require_landlord_or_creator(current_user: User = Depends(get_current_user)) -> User:
    """
    Landlords (own listings) OR staff holding listings.create, so the Landlord
    Acquisition Lead can add properties on a landlord's behalf.
    """
    from app.core.permissions import has_permission
    if current_user.role == "landlord":
        return current_user
    if has_permission(getattr(current_user, "role", ""), "listings.create"):
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord access required.")


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
        raise HTTPException(status_code=500, detail="Image upload failed. Please try again.")


def _cloudinary_upload_media(data: bytes, vm: "mv.ValidatedMedia") -> dict:
    """Upload validated bytes with the right Cloudinary resource_type."""
    resource_type = "image" if vm.media_type == MediaType.PHOTO else "video"
    kwargs = dict(folder="findmynyumba/properties", resource_type=resource_type)
    if resource_type == "image":
        kwargs["transformation"] = [{"width": 1200, "crop": "limit", "quality": "auto"}]
    try:
        return cloudinary.uploader.upload(data, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Media upload failed: {e}")


async def _process_media_uploads(files: List[UploadFile], listing_id: int, db: Session,
                                 *, make_first_cover: bool = True) -> List[ListingMedia]:
    """Validate ALL -> Cloudinary -> ListingMedia rows. Mirrors the student-host flow."""
    real = [f for f in files if f and f.filename]
    if not real:
        return []
    existing = db.query(ListingMedia).filter(ListingMedia.listing_id == listing_id).count()
    mv.validate_added_count(existing, len(real))
    staged = []
    for f in real:
        data = await f.read()
        vm = mv.validate_file(f.filename, data)
        staged.append((vm, data, f.filename))
    has_cover = (db.query(ListingMedia)
                   .filter(ListingMedia.listing_id == listing_id, ListingMedia.is_cover.is_(True))
                   .count() > 0)
    created: List[ListingMedia] = []
    pos = existing
    for idx, (vm, data, fname) in enumerate(staged):
        res = _cloudinary_upload_media(data, vm)
        is_cover = make_first_cover and (not has_cover) and idx == 0
        # Perceptual hash for duplicate detection (photos only; never raises).
        img_hash = phash_bytes(data) if vm.media_type == MediaType.PHOTO else None
        row = ListingMedia(
            listing_id=listing_id,
            media_url=res.get("secure_url") or res.get("url"),
            public_id=res.get("public_id"),
            resource_type=res.get("resource_type"),
            media_type=vm.media_type.value,
            file_name=fname, file_size=vm.size_bytes, mime_type=vm.mime_type,
            width=res.get("width"), height=res.get("height"), duration=res.get("duration"),
            position=pos, is_cover=is_cover,
            image_hash=img_hash,
        )
        db.add(row); created.append(row); pos += 1
        if is_cover: has_cover = True
    return created


def _media_response(m: ListingMedia) -> dict:
    return {
        "id": m.id, "listing_id": m.listing_id, "media_url": m.media_url,
        "media_type": m.media_type, "public_id": m.public_id,
        "width": m.width, "height": m.height, "duration": m.duration,
        "position": m.position, "is_cover": m.is_cover,
    }


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


# â”€â”€ Dashboard Stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# â”€â”€ Properties â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            "media":      [_media_response(m) for m in (l.media or [])],
            "cover_url":  _absolute_image_url(l.cover_url, request),
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in listings
    ]


@router.post("/properties", status_code=201)
async def create_property(
    title:       str = Form(..., min_length=2, max_length=160),
    price:       float = Form(..., ge=0),
    location:    str = Form(..., min_length=2, max_length=200),
    description: str = Form(..., min_length=5, max_length=4000),
    images:      Optional[List[UploadFile]] = File(None),
    media:       Optional[List[UploadFile]] = File(None),
    owner_id:    Optional[int] = Form(None),
    landlord:    User    = Depends(require_landlord_or_creator),
    db:          Session = Depends(get_db),
):
    # Staff with listings.create may file a property under an existing landlord.
    _target_owner_id = landlord.id
    if owner_id is not None and owner_id != landlord.id:
        from app.core.permissions import has_permission
        if not has_permission(getattr(landlord, "role", ""), "listings.create"):
            raise HTTPException(status_code=403, detail="Not allowed to create listings for another user.")
        _target = db.query(User).filter(User.id == owner_id, User.role == "landlord").first()
        if not _target:
            raise HTTPException(status_code=404, detail="Landlord not found.")
        _target_owner_id = _target.id
    # Backward compatible: legacy `images` (photos only) still works and is used
    # only when the new `media` field (photos + videos) is absent.
    first_image_url = None
    if images and not media:
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
        image_url   = first_image_url,
        status      = "pending",
        owner_id    = _target_owner_id,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)

    if media:
        try:
            created = await _process_media_uploads(media, listing.id, db, make_first_cover=True)
        except mv.MediaValidationError as e:
            db.delete(listing); db.commit()
            raise HTTPException(status_code=400, detail=e.message)
        cover = next((m for m in created if m.is_cover), None) or (created[0] if created else None)
        if cover and not listing.image_url:
            listing.image_url = cover.media_url
        db.commit(); db.refresh(listing)

    return {"status": "success", "message": "Property submitted for review!", "id": listing.id}


@router.put("/properties/{listing_id}")
async def update_property(
    listing_id:  int,
    title:       str = Form(..., min_length=2, max_length=160),
    price:       float = Form(..., ge=0),
    location:    str = Form(..., min_length=2, max_length=200),
    description: str = Form(..., min_length=5, max_length=4000),
    images:      Optional[List[UploadFile]] = File(None),
    media:       Optional[List[UploadFile]] = File(None),
    owner_id:    Optional[int] = Form(None),
    landlord:    User    = Depends(require_landlord_or_creator),
    db:          Session = Depends(get_db),
):
    # Staff with listings.create may file a property under an existing landlord.
    _target_owner_id = landlord.id
    if owner_id is not None and owner_id != landlord.id:
        from app.core.permissions import has_permission
        if not has_permission(getattr(landlord, "role", ""), "listings.create"):
            raise HTTPException(status_code=403, detail="Not allowed to create listings for another user.")
        _target = db.query(User).filter(User.id == owner_id, User.role == "landlord").first()
        if not _target:
            raise HTTPException(status_code=404, detail="Landlord not found.")
        _target_owner_id = _target.id
    listing = db.query(Listing).filter(Listing.id == listing_id, Listing.owner_id == landlord.id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Property not found.")

    listing.title       = title.strip()
    listing.description = description.strip()
    listing.price       = price
    listing.location    = location.strip()

    # Legacy images path (photos only) â€” used only when no `media` provided.
    if images and not media:
        for img in images[:10]:
            if not img.filename:
                continue
            url = await _upload_to_cloudinary(img)
            listing.image_url = url
            break

    db.commit()
    db.refresh(listing)

    if media:
        try:
            created = await _process_media_uploads(media, listing.id, db, make_first_cover=True)
        except mv.MediaValidationError as e:
            raise HTTPException(status_code=400, detail=e.message)
        if not listing.image_url:
            cover = next((m for m in created if m.is_cover), None) or (created[0] if created else None)
            if cover:
                listing.image_url = cover.media_url
        db.commit(); db.refresh(listing)

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
        "media":       [_media_response(m) for m in (listing.media or [])],
        "cover_url":   _absolute_image_url(listing.cover_url, request),
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


# â”€â”€ Inquiries â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# â”€â”€ Verification â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/verification")
def get_verification(landlord: User = Depends(require_landlord)):
    return {"verification_status": landlord.verification_status or "unverified", "rejection_reason": landlord.verification_rejection_reason or None}


@router.post("/verify")
async def submit_verification(doc1: UploadFile = File(...), doc2: UploadFile = File(...), landlord: User = Depends(require_landlord), db: Session = Depends(get_db)):
    if landlord.verification_status == "pending":
        raise HTTPException(status_code=409, detail="A verification request is already pending review.")
    landlord.verification_doc1_url = await _upload_doc_to_cloudinary(doc1, landlord.id, "doc1")
    landlord.verification_doc2_url = await _upload_doc_to_cloudinary(doc2, landlord.id, "doc2")
    landlord.verification_status = "pending"
    landlord.verification_rejection_reason = None
    db.commit()
    return {"status": "success", "message": "Verification documents submitted."}


# â”€â”€ Profile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# â”€â”€ Profile photo (avatar) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def _upload_avatar_to_cloudinary(f: UploadFile) -> str:
    """Upload a profile photo to Cloudinary (square, face-aware crop)."""
    mime = (f.content_type or "").lower()
    if mime not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime}.")
    data = await f.read()
    if len(data) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_IMAGE_SIZE_MB}MB limit.")
    try:
        result = cloudinary.uploader.upload(
            data,
            folder="findmynyumba/avatars",
            resource_type="image",
            transformation=[{"width": 400, "height": 400, "crop": "fill",
                             "gravity": "face", "quality": "auto"}],
        )
        return result["secure_url"]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Photo upload failed. Please try again.")


@router.post("/profile/photo")
async def upload_profile_photo(
    file:     UploadFile = File(...),
    landlord: User    = Depends(require_landlord),
    db:       Session = Depends(get_db),
):
    url = await _upload_avatar_to_cloudinary(file)
    landlord.avatar_url = url
    db.commit()
    return {"status": "success", "avatar_url": url}


# â”€â”€ Change Password â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# -- GET /landlord/reviews --------------------------------------------------
# All reviews across listings this landlord owns, newest first, each with the
# listing title, reviewer name, rating, comment, status, and any existing
# host reply. Lets the host see and reply to reviews from their dashboard.
@router.get("/reviews")
def landlord_reviews(
    current_user: User = Depends(require_landlord),
    db: Session = Depends(get_db),
):
    listing_ids = [lid for (lid,) in db.query(Listing.id).filter(Listing.owner_id == current_user.id).all()]
    if not listing_ids:
        return {"count": 0, "average": None, "reviews": []}
    titles = {l.id: l.title for l in db.query(Listing).filter(Listing.id.in_(listing_ids)).all()}
    rows = (
        db.query(Review)
          .filter(Review.listing_id.in_(listing_ids))
          .order_by(Review.created_at.desc())
          .all()
    )
    out = []
    approved_ratings = []
    for r in rows:
        if r.status == "approved":
            approved_ratings.append(r.rating)
        out.append({
            "id": r.id,
            "listing_id": r.listing_id,
            "listing_title": titles.get(r.listing_id, f"Listing #{r.listing_id}"),
            "reviewer_name": r.user_name or "Student",
            "rating": r.rating,
            "comment": r.comment,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reply_text": r.reply_text,
            "reply_at": r.reply_at.isoformat() if r.reply_at else None,
            "rating_accuracy": r.rating_accuracy,
            "rating_landlord": r.rating_landlord,
            "rating_value": r.rating_value,
        })
    avg = round(sum(approved_ratings) / len(approved_ratings), 1) if approved_ratings else None
    return {"count": len(approved_ratings), "average": avg, "reviews": out}
