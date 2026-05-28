"""
app/api/v1/endpoints/uploads.py

Endpoints:
  POST /uploads/listing-images  — upload 1–8 photos for a listing (multipart)
  POST /uploads/avatar          — upload/replace the current user's profile photo
  POST /uploads/image           — legacy single-image upload (kept for back-compat)

Security:
  - All endpoints require a valid JWT (get_current_user).
  - File type validated by content_type AND magic bytes (first 12 bytes).
  - Size enforced AFTER reading bytes (file.size is None for streamed uploads).
  - Cloudinary credentials come from settings, never hardcoded.
  - Filenames are never trusted or stored — Cloudinary assigns its own public_id.

Storage:
  - Listing images: returned as a list; caller (listing create/update route)
    writes the URLs to the Listing.images column.
  - Avatar: written directly to User.avatar_url and committed here.
"""

import logging
from typing import List

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(tags=["Uploads"])
log = logging.getLogger("findmynyumba.uploads")

# ── Cloudinary — configured once from settings ────────────────────────────────
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_FILE_BYTES   = 5 * 1024 * 1024   # 5 MB per file
MAX_LISTING_IMGS = 8

# MIME types we accept
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# Magic-byte signatures (offset, bytes) — defend against MIME-spoofing
MAGIC = [
    (0, b"\xff\xd8\xff"),                        # JPEG
    (0, b"\x89PNG\r\n\x1a\n"),                   # PNG
    (0, b"RIFF"),                                # WebP (RIFF....WEBP)
    (0, b"GIF87a"), (0, b"GIF89a"),              # GIF
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _validate_image_bytes(data: bytes, filename: str) -> None:
    """Raise HTTPException if bytes are not a known safe image format."""
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"'{filename}' exceeds the 5 MB limit.",
        )
    head = data[:12]
    for offset, sig in MAGIC:
        if head[offset: offset + len(sig)] == sig:
            return
    raise HTTPException(
        status_code=400,
        detail=f"'{filename}' is not a supported image (JPEG, PNG, WebP, GIF).",
    )


def _upload_to_cloudinary(data: bytes, folder: str, transformation: list) -> str:
    """Upload raw bytes to Cloudinary and return the secure URL."""
    try:
        result = cloudinary.uploader.upload(
            data,
            folder=folder,
            resource_type="image",
            transformation=transformation,
        )
        return result["secure_url"]
    except Exception as exc:
        log.error("Cloudinary upload failed: %s", exc)
        raise HTTPException(status_code=500, detail="Image upload failed. Please try again.")


# ── POST /uploads/listing-images ──────────────────────────────────────────────
@router.post("/listing-images")
async def upload_listing_images(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Accept 1–8 images for a listing.
    Returns { "image_urls": ["https://...", ...] }

    The caller (listing create/update route) is responsible for persisting
    these URLs to the Listing.images column.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) > MAX_LISTING_IMGS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_LISTING_IMGS} images per listing.",
        )

    # Validate content-type header first (fast reject)
    for f in files:
        if f.content_type not in ALLOWED_MIME:
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}' has unsupported type '{f.content_type}'. "
                       "Allowed: JPEG, PNG, WebP, GIF.",
            )

    urls: List[str] = []
    for f in files:
        data = await f.read()
        _validate_image_bytes(data, f.filename or "file")
        url = _upload_to_cloudinary(
            data,
            folder="findmynyumba/properties",
            transformation=[{"width": 1200, "crop": "limit", "quality": "auto:good"}],
        )
        urls.append(url)

    return {"image_urls": urls}


# ── POST /uploads/avatar ──────────────────────────────────────────────────────
@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload or replace the current user's profile photo.
    Saves the Cloudinary URL to User.avatar_url and returns it.
    Returns { "avatar_url": "https://..." }
    """
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: JPEG, PNG, WebP, GIF.",
        )

    data = await file.read()
    _validate_image_bytes(data, file.filename or "avatar")

    url = _upload_to_cloudinary(
        data,
        folder=f"findmynyumba/avatars",
        transformation=[
            {"width": 400, "height": 400, "crop": "fill", "gravity": "face", "quality": "auto:good"}
        ],
    )

    # Persist to DB
    try:
        current_user.avatar_url = url
        db.commit()
        db.refresh(current_user)
    except Exception as exc:
        db.rollback()
        log.error("Failed to save avatar_url for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to save profile photo.")

    return {"avatar_url": url}


# ── POST /uploads/image  (legacy single-image — kept for back-compat) ─────────
@router.post("/image")
async def upload_single_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Legacy endpoint — upload a single listing image.
    Prefer /uploads/listing-images for new code.
    Returns { "image_url": "https://..." }
    """
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="File must be a JPEG, PNG, WebP, or GIF image.")

    data = await file.read()
    _validate_image_bytes(data, file.filename or "file")

    url = _upload_to_cloudinary(
        data,
        folder="findmynyumba/properties",
        transformation=[{"width": 1200, "crop": "limit", "quality": "auto:good"}],
    )
    return {"image_url": url}
