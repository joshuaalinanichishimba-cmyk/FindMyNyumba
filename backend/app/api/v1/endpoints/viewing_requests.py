"""
app/api/v1/endpoints/viewing_requests.py

Viewing-request lifecycle endpoints.

  POST  /viewing-requests                 student creates a request   -> pending
  GET   /viewing-requests/landlord        landlord's incoming requests
  GET   /viewing-requests/student         student's sent requests
  PATCH /viewing-requests/{id}/respond    landlord accepts / rejects  (+ landlord_notes, rejection_reason)
  PATCH /viewing-requests/{id}/reschedule landlord proposes new slot  -> rescheduled
  PATCH /viewing-requests/{id}/cancel     student withdraws own request -> cancelled

WHAT CHANGED IN THIS VERSION
----------------------------
1. Every state change now writes a REAL in-app notification via
   app.core.notify.push_notification (was a no-op stub).
2. On ACCEPT, an approval message is auto-posted into the existing chat
   (Message table) from the landlord to the student, e.g.
   "Your viewing request for Room A has been approved for 2026-08-14 at 10:00."
3. /respond accepts an optional `rejection_reason` (Property no longer
   available | Time slot unavailable | Request incomplete | Other) which is
   folded into landlord_notes and the student's notification body.

SECURITY (unchanged): only the assigned landlord may respond/reschedule; only
the owning student may cancel; a landlord cannot request their own listing.
"""
import secrets
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.notify import (
    push_notification,
    VIEWING_REQUESTED, VIEWING_APPROVED, VIEWING_REJECTED,
    VIEWING_RESCHEDULED, VIEWING_CANCELLED,
)
from app.models.listing import Listing
from app.models.message import Message
from app.models.user import User
from app.models.viewing_request import ViewingRequest, ViewingStatus

router = APIRouter(prefix="/viewing-requests", tags=["Viewing Requests"])

_RESPONDABLE   = {ViewingStatus.PENDING.value, ViewingStatus.RESCHEDULED.value}
_RESCHEDULABLE = {ViewingStatus.PENDING.value, ViewingStatus.ACCEPTED.value, ViewingStatus.RESCHEDULED.value}
_CANCELLABLE   = {ViewingStatus.PENDING.value, ViewingStatus.ACCEPTED.value, ViewingStatus.RESCHEDULED.value}

_LEGACY_MAP = {"confirmed": "accepted", "declined": "rejected"}

# Allowed canned rejection reasons (free text "Other" also accepted).
_REJECTION_REASONS = {
    "Property no longer available",
    "Time slot unavailable",
    "Request incomplete",
    "Other",
}


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _validate_future(date_str: str, time_str: str) -> None:
    if not date_str or not time_str:
        raise HTTPException(status_code=400, detail="Please choose a date and time.")
    try:
        chosen = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format (use YYYY-MM-DD and HH:MM).")
    if chosen < datetime.now():
        raise HTTPException(status_code=400, detail="Please choose a future date and time.")


def _maybe_expire(vr: ViewingRequest) -> bool:
    if vr.status != ViewingStatus.PENDING.value:
        return False
    try:
        slot = datetime.strptime(f"{vr.preferred_date} {vr.preferred_time}", "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return False
    if slot < datetime.now():
        vr.status = ViewingStatus.EXPIRED.value
        return True
    return False


def _post_chat_message(db: Session, vr: ViewingRequest, text: str) -> None:
    """Auto-post a system-style chat message from landlord -> student, tied to
    the listing so it threads under the right property conversation. Best-effort:
    a chat failure must not break the viewing action."""
    try:
        db.add(Message(
            sender_id=vr.landlord_id,
            receiver_id=vr.student_id,
            property_id=vr.listing_id,
            content=text,
            is_read=False,
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _serialize(v: ViewingRequest, include_code: bool = False) -> dict:
    display_status = _LEGACY_MAP.get(v.status, v.status)
    return {
        "id": v.id,
        "listing_id": v.listing_id,
        "property_id": v.listing_id,
        "listing_title": v.listing.title if v.listing else None,
        "student_id": v.student_id,
        "student_name": v.student.full_name if v.student else None,
        "student_phone": v.student.phone_number if v.student else None,
        "landlord_id": v.landlord_id,
        "landlord_name": v.landlord.full_name if v.landlord else None,
        "preferred_date": v.preferred_date,
        "preferred_time": v.preferred_time,
        "rescheduled_date": v.rescheduled_date,
        "rescheduled_time": v.rescheduled_time,
        "notes": v.notes,
        "landlord_notes": v.landlord_notes,
        "status": display_status,
        "viewing_code": (v.viewing_code if include_code else None),
        "code_verified": v.code_verified,
        "completed_at": v.completed_at.isoformat() if v.completed_at else None,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


# â”€â”€ Request bodies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ViewingCreate(BaseModel):
    listing_id: int
    preferred_date: str
    preferred_time: str
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _accept_aliases(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            if data.get("listing_id") is None and data.get("property_id") is not None:
                data["listing_id"] = data["property_id"]
            if data.get("preferred_date") is None and data.get("date") is not None:
                data["preferred_date"] = data["date"]
            if data.get("preferred_time") is None and data.get("time") is not None:
                data["preferred_time"] = data["time"]
        return data


class RespondBody(BaseModel):
    status: str                              # "accepted" | "rejected"
    landlord_notes: Optional[str] = None
    rejection_reason: Optional[str] = None   # one of _REJECTION_REASONS (or free text when "Other")


class RescheduleBody(BaseModel):
    rescheduled_date: str
    rescheduled_time: str
    landlord_notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _accept_aliases(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            if data.get("rescheduled_date") is None and data.get("date") is not None:
                data["rescheduled_date"] = data["date"]
            if data.get("rescheduled_time") is None and data.get("time") is not None:
                data["rescheduled_time"] = data["time"]
        return data


# â”€â”€ Create (student) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.post("", status_code=status.HTTP_201_CREATED)
def create_viewing_request(
    body: ViewingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == body.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    if listing.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot request a viewing of your own listing.")

    _validate_future(body.preferred_date, body.preferred_time)

    vr = ViewingRequest(
        listing_id=listing.id,
        student_id=current_user.id,
        landlord_id=listing.owner_id,
        preferred_date=body.preferred_date,
        preferred_time=body.preferred_time,
        notes=(body.notes or "").strip() or None,
        status=ViewingStatus.PENDING.value,
    )
    db.add(vr)
    db.commit()
    db.refresh(vr)

    push_notification(
        db, vr.landlord_id, VIEWING_REQUESTED,
        "New viewing request",
        f"{current_user.full_name or 'A student'} requested to view "
        f"{listing.title} on {vr.preferred_date} at {vr.preferred_time}.",
    )

    return {"status": "success",
            "message": "Viewing requested. The landlord will respond shortly.",
            "request": _serialize(vr)}


# â”€â”€ Landlord: incoming requests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/landlord")
def landlord_viewing_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ViewingRequest)
        .filter(ViewingRequest.landlord_id == current_user.id)
        .order_by(ViewingRequest.created_at.desc())
        .all()
    )
    if any(_maybe_expire(v) for v in rows):
        db.commit()
    return [_serialize(v) for v in rows]


# â”€â”€ Student: sent requests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/student")
def student_viewing_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ViewingRequest)
        .filter(ViewingRequest.student_id == current_user.id)
        .order_by(ViewingRequest.created_at.desc())
        .all()
    )
    if any(_maybe_expire(v) for v in rows):
        db.commit()
    return [_serialize(v, include_code=True) for v in rows]


def _load_for_landlord(viewing_id: int, current_user: User, db: Session) -> ViewingRequest:
    vr = db.query(ViewingRequest).filter(ViewingRequest.id == viewing_id).first()
    if not vr:
        raise HTTPException(status_code=404, detail="Viewing request not found.")
    if current_user.id != vr.landlord_id:
        raise HTTPException(status_code=403, detail="Only the listing's landlord can manage this request.")
    return vr


# â”€â”€ Landlord: accept / reject â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_VIEWING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # excludes ambiguous O/0/I/1


def _generate_viewing_code(db: Session) -> str:
    """Return a unique, unguessable FMN-XXXXXX viewing code."""
    for _ in range(10):
        code = "FMN-" + "".join(secrets.choice(_VIEWING_CODE_ALPHABET) for _ in range(6))
        exists = db.query(ViewingRequest).filter(ViewingRequest.viewing_code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="Could not generate a unique viewing code. Please retry.")


@router.patch("/{viewing_id}/respond")
def respond_to_viewing(
    viewing_id: int,
    body: RespondBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vr = _load_for_landlord(viewing_id, current_user, db)

    new_status = (body.status or "").strip().lower()
    if new_status not in {ViewingStatus.ACCEPTED.value, ViewingStatus.REJECTED.value}:
        raise HTTPException(status_code=400, detail="Status must be 'accepted' or 'rejected'.")
    if vr.status not in _RESPONDABLE:
        raise HTTPException(status_code=409, detail=f"Cannot respond to a request that is '{vr.status}'.")

    # Fold an optional rejection reason into landlord_notes.
    note = (body.landlord_notes or "").strip()
    if new_status == ViewingStatus.REJECTED.value and body.rejection_reason:
        reason = body.rejection_reason.strip()
        note = f"{reason} - {note}".strip(" -") if note else reason

    vr.status = new_status
    if note:
        vr.landlord_notes = note
    db.commit()
    db.refresh(vr)

    title = vr.listing.title if vr.listing else "your listing"

    if new_status == ViewingStatus.ACCEPTED.value:
        # Generate a unique viewing code on first acceptance (stable across
        # later reschedules). The student shows it; the landlord verifies it
        # at the physical viewing to mark the viewing completed.
        if not vr.viewing_code:
            vr.viewing_code = _generate_viewing_code(db)
            db.commit()
            db.refresh(vr)
        # Auto-post the approval message into chat (brief's wording).
        _post_chat_message(
            db, vr,
            f"Your viewing request for {title} has been approved for "
            f"{vr.preferred_date} at {vr.preferred_time}.",
        )
        push_notification(
            db, vr.student_id, VIEWING_APPROVED,
            "Viewing approved",
            f"Your viewing for {title} is confirmed for {vr.preferred_date} at {vr.preferred_time}.",
        )
    else:
        push_notification(
            db, vr.student_id, VIEWING_REJECTED,
            "Viewing declined",
            "Unfortunately your viewing request has been declined."
            + (f" Reason: {vr.landlord_notes}." if vr.landlord_notes else ""),
        )

    return {"status": "success", "request": _serialize(vr)}


# â”€â”€ Landlord: reschedule â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.patch("/{viewing_id}/reschedule")
def reschedule_viewing(
    viewing_id: int,
    body: RescheduleBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vr = _load_for_landlord(viewing_id, current_user, db)
    if vr.status not in _RESCHEDULABLE:
        raise HTTPException(status_code=409, detail=f"Cannot reschedule a request that is '{vr.status}'.")

    _validate_future(body.rescheduled_date, body.rescheduled_time)

    vr.status = ViewingStatus.RESCHEDULED.value
    vr.rescheduled_date = body.rescheduled_date
    vr.rescheduled_time = body.rescheduled_time
    # A rescheduled viewing is still a confirmed slot the student will attend,
    # so it needs a code too (generate once, stable thereafter).
    if not vr.viewing_code:
        vr.viewing_code = _generate_viewing_code(db)
    if body.landlord_notes is not None:
        vr.landlord_notes = body.landlord_notes.strip() or None
    db.commit()
    db.refresh(vr)

    title = vr.listing.title if vr.listing else "your listing"
    _post_chat_message(
        db, vr,
        f"Your viewing request for {title} has been rescheduled to "
        f"{vr.rescheduled_date} at {vr.rescheduled_time}."
        + (f" Note: {vr.landlord_notes}" if vr.landlord_notes else ""),
    )
    push_notification(
        db, vr.student_id, VIEWING_RESCHEDULED,
        "Viewing rescheduled",
        f"New proposed time for {title}: {vr.rescheduled_date} at {vr.rescheduled_time}. "
        "Open your requests to accept or decline.",
    )

    return {"status": "success", "request": _serialize(vr)}


# â”€â”€ Student: cancel own request â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.patch("/{viewing_id}/cancel")
def cancel_viewing(
    viewing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vr = db.query(ViewingRequest).filter(ViewingRequest.id == viewing_id).first()
    if not vr:
        raise HTTPException(status_code=404, detail="Viewing request not found.")
    if current_user.id != vr.student_id:
        raise HTTPException(status_code=403, detail="You can only cancel your own request.")
    if vr.status not in _CANCELLABLE:
        raise HTTPException(status_code=409, detail=f"Cannot cancel a request that is '{vr.status}'.")

    vr.status = ViewingStatus.CANCELLED.value
    db.commit()
    db.refresh(vr)

    title = vr.listing.title if vr.listing else "your listing"
    push_notification(
        db, vr.landlord_id, VIEWING_CANCELLED,
        "Viewing cancelled",
        f"{vr.student.full_name if vr.student else 'A student'} cancelled their viewing for {title}.",
    )

    return {"status": "success", "request": _serialize(vr)}


# ── Landlord: complete (verify code) / missed ───────────────────────────────
class CompleteBody(BaseModel):
    code: str


@router.patch("/{viewing_id}/complete")
def complete_viewing(
    viewing_id: int,
    body: CompleteBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Landlord verifies the student's viewing code at the physical viewing,
    marking it completed. This is the trust signal that later gates reviews."""
    vr = _load_for_landlord(viewing_id, current_user, db)
    if vr.status not in {ViewingStatus.ACCEPTED.value, ViewingStatus.RESCHEDULED.value}:
        raise HTTPException(status_code=409, detail="Only an accepted viewing can be marked completed.")
    if not vr.viewing_code:
        raise HTTPException(status_code=400, detail="This viewing has no code to verify.")
    submitted = (body.code or "").strip().upper()
    if submitted != vr.viewing_code.upper():
        raise HTTPException(status_code=400, detail="Code does not match. Ask the student for the code shown in their dashboard.")

    vr.status = ViewingStatus.COMPLETED.value
    vr.code_verified = True
    vr.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(vr)

    title = vr.listing.title if vr.listing else "the property"
    push_notification(
        db, vr.student_id, VIEWING_APPROVED,
        "Viewing completed",
        f"Your viewing for {title} has been confirmed as completed. You can now leave a review.",
    )
    return {"status": "success", "request": _serialize(vr)}


@router.patch("/{viewing_id}/missed")
def mark_viewing_missed(
    viewing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Landlord marks an accepted viewing as a no-show."""
    vr = _load_for_landlord(viewing_id, current_user, db)
    if vr.status not in {ViewingStatus.ACCEPTED.value, ViewingStatus.RESCHEDULED.value}:
        raise HTTPException(status_code=409, detail="Only an accepted viewing can be marked missed.")
    vr.status = ViewingStatus.MISSED.value
    db.commit()
    db.refresh(vr)
    return {"status": "success", "request": _serialize(vr)}
