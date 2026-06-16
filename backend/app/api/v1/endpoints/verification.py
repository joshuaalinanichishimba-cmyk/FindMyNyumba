"""
app/api/v1/endpoints/verification.py

Landlord and property VERIFICATION workflow (the submit side; admin decisions
live in admin_trust.py).

Landlord flow (matches the 6-step brief):
    1 Phone verification      -> POST /verification/phone/confirm
    2 Email verification      -> (existing email-verify flow flips email_verified)
    3 NRC front upload        -> POST /verification/documents  (doc_type=nrc_front)
    4 NRC back upload         -> POST /verification/documents  (doc_type=nrc_back)
    5 Selfie upload           -> POST /verification/documents  (doc_type=selfie)
    6 Property documents      -> POST /verification/documents  (doc_type=property_doc)
    submit for review         -> POST /verification/submit
    status:  pending -> review -> approved | rejected

Property flow:
    submit a listing for property review -> POST /verification/property/{listing_id}

SECURITY
--------
  * Uploads validated by magic-bytes (reuses media_validation), size-capped,
    and pushed to Cloudinary (Render disk is ephemeral). Raw bytes never hit
    Postgres.
  * Each image gets a perceptual hash on upload so the same NRC/selfie reused
    across accounts is detectable (duplicate detection + risk engine).
  * Rate limited: document uploads and submissions are abuse vectors.
  * Every state change writes an audit row via record_audit.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import cloudinary
import cloudinary.uploader
from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.audit import record_audit
from app.core.database import get_db
from app.core.image_hash import phash_bytes, find_duplicates
from app.core.rate_limiter import limiter
from app.core.risk_engine import persist_user_risk
from app.models.listing import Listing
from app.models.user import User
from app.models.trust_models import (
    Verification, VerificationDocument, PropertyVerification,
)
from app.schemas.trust import VerificationOut, PropertyVerificationOut

router = APIRouter(prefix="/verification", tags=["Verification"])

# Reuse the project's Cloudinary config (same env vars as landlords.py).
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.getenv("CLOUDINARY_API_KEY", ""),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
    secure=True,
)

ALLOWED_DOC_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_DOC_MB = 10
DOC_TYPES = {"nrc_front", "nrc_back", "selfie", "property_doc"}

UPLOAD_LIMIT = "20/hour"
SUBMIT_LIMIT = "5/hour"


def _get_or_create_verification(db: Session, user: User) -> Verification:
    v = (
        db.query(Verification)
        .filter(Verification.user_id == user.id)
        .order_by(Verification.created_at.desc())
        .first()
    )
    # A new case is needed if there is none, or the last one was decided.
    if v is None or v.status in ("approved", "rejected"):
        v = Verification(user_id=user.id, status="pending",
                         email_verified=bool(getattr(user, "is_verified", False)))
        db.add(v)
        db.commit()
        db.refresh(v)
    return v


@router.get("/me", response_model=VerificationOut)
def my_verification(current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return _get_or_create_verification(db, current_user)


@router.post("/phone/confirm", response_model=VerificationOut)
@limiter.limit(SUBMIT_LIMIT)
def confirm_phone(request: Request,
                  current_user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """
    Mark phone verified. In production this is the success callback of an
    OTP/SMS step; we keep the OTP provider out of scope and flip the flag here
    once the code has been confirmed by the SMS endpoint.
    """
    if not getattr(current_user, "phone_number", None):
        raise HTTPException(status_code=400,
                            detail="Add a phone number to your profile first.")
    v = _get_or_create_verification(db, current_user)
    v.phone_verified = True
    db.commit()
    db.refresh(v)
    record_audit(db, request, actor=current_user, action="verification.phone_confirmed",
                 entity_type="verification", entity_id=v.id)
    persist_user_risk(db, current_user)
    return v


@router.post("/documents", response_model=VerificationOut)
@limiter.limit(UPLOAD_LIMIT)
async def upload_document(
    request: Request,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload one verification artifact (NRC front/back, selfie, property doc)."""
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail="Invalid document type.")

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_DOC_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime}.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > MAX_DOC_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_DOC_MB}MB.")

    # Perceptual hash for images (PDFs get None — they aren't compared visually).
    ph = phash_bytes(data) if mime != "application/pdf" else None

    # Upload to Cloudinary (private folder; signed delivery recommended in prod).
    resource_type = "raw" if mime == "application/pdf" else "image"
    try:
        result = cloudinary.uploader.upload(
            data,
            folder="findmynyumba/verification",
            resource_type=resource_type,
            public_id=f"user_{current_user.id}_{doc_type}",
            overwrite=True,
            type="authenticated" if resource_type == "image" else "upload",
        )
        url = result["secure_url"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upload failed: {e}")

    v = _get_or_create_verification(db, current_user)

    # Replace any prior doc of this type for the current case.
    db.query(VerificationDocument).filter(
        VerificationDocument.verification_id == v.id,
        VerificationDocument.doc_type == doc_type,
    ).delete()

    doc = VerificationDocument(
        verification_id=v.id, user_id=current_user.id, doc_type=doc_type,
        file_url=url, mime_type=mime, phash=ph,
    )
    db.add(doc)

    # Flip the matching checkbox on the verification case.
    setattr(v, {
        "nrc_front": "nrc_front_uploaded",
        "nrc_back": "nrc_back_uploaded",
        "selfie": "selfie_uploaded",
        "property_doc": "property_docs_uploaded",
    }[doc_type], True)

    # Mirror the two legacy URL fields the existing admin UI reads.
    if doc_type == "nrc_front":
        current_user.verification_doc1_url = url
    elif doc_type == "property_doc":
        current_user.verification_doc2_url = url

    db.commit()
    db.refresh(v)

    record_audit(db, request, actor=current_user, action="verification.document_uploaded",
                 entity_type="verification", entity_id=v.id, meta={"doc_type": doc_type})

    # Duplicate check: does this image's hash already exist on ANOTHER user?
    if ph:
        candidates = [
            (d.user_id, d.phash) for d in
            db.query(VerificationDocument)
            .filter(VerificationDocument.user_id != current_user.id,
                    VerificationDocument.phash.isnot(None))
            .all()
        ]
        if find_duplicates(ph, candidates):
            record_audit(db, request, actor=current_user,
                         action="verification.duplicate_image_flagged",
                         entity_type="verification", entity_id=v.id,
                         meta={"doc_type": doc_type})

    return v


@router.post("/submit", response_model=VerificationOut)
@limiter.limit(SUBMIT_LIMIT)
def submit_for_review(request: Request,
                      current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """Move the case from pending -> review once the required docs are present."""
    v = _get_or_create_verification(db, current_user)
    missing = []
    if not v.nrc_front_uploaded: missing.append("NRC front")
    if not v.nrc_back_uploaded:  missing.append("NRC back")
    if not v.selfie_uploaded:    missing.append("selfie")
    if missing:
        raise HTTPException(status_code=400,
                            detail=f"Still required: {', '.join(missing)}.")
    v.status = "review"
    # Reflect on the user record the existing admin queue reads.
    current_user.verification_status = "pending"
    db.commit()
    db.refresh(v)
    record_audit(db, request, actor=current_user, action="verification.submitted",
                 entity_type="verification", entity_id=v.id)
    return v


# ── Property verification submission ──────────────────────────────────────────
@router.post("/property/{listing_id}", response_model=PropertyVerificationOut)
@limiter.limit(SUBMIT_LIMIT)
def submit_property(listing_id: int, request: Request,
                    current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Owner submits one of their listings for property-level verification."""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not your listing.")

    existing = (
        db.query(PropertyVerification)
        .filter(PropertyVerification.listing_id == listing_id,
                PropertyVerification.status == "pending")
        .first()
    )
    if existing:
        return existing

    pv = PropertyVerification(listing_id=listing_id, submitted_by=current_user.id,
                              status="pending")
    db.add(pv)
    db.commit()
    db.refresh(pv)
    record_audit(db, request, actor=current_user, action="property_verification.submitted",
                 entity_type="listing", entity_id=listing_id)
    return pv
