"""
app/api/v1/endpoints/viewing_requests.py

Endpoints for the viewing-request feature.

  POST  /viewings            student requests a viewing
  GET   /viewings/mine       requests the current user made (as a student)
  GET   /viewings/incoming   requests for the current user's listings (as landlord)
  PATCH /viewings/{id}       landlord confirms / declines / completes a request

Authorization is enforced per-endpoint: a student can only see their own
requests; a landlord can only see/act on requests for listings they own.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.listing import Listing
from app.models.user import User
from app.models.viewing_request import ViewingRequest

router = APIRouter(prefix="/viewings", tags=["Viewings"])

# Statuses a landlord is allowed to set.
LANDLORD_STATUSES = {"confirmed", "declined", "completed"}
# Statuses a student is allowed to set (just cancelling their own request).
STUDENT_STATUSES = {"cancelled"}


# ── Request bodies ────────────────────────────────────────────────────────
class ViewingCreate(BaseModel):
    listing_id: int
    date: str            # "YYYY-MM-DD"
    time: str            # "HH:MM"
    notes: str | None = None


class ViewingStatusUpdate(BaseModel):
    status: str


def _serialize(v: ViewingRequest) -> dict:
    return {
        "id": v.id,
        "listing_id": v.listing_id,
        "listing_title": v.listing.title if v.listing else None,
        "student_id": v.student_id,
        "student_name": v.student.full_name if v.student else None,
        "landlord_id": v.landlord_id,
        "preferred_date": v.preferred_date,
        "preferred_time": v.preferred_time,
        "notes": v.notes,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


# ── Create ────────────────────────────────────────────────────────────────
@router.post("", status_code=status.HTTP_201_CREATED)
def create_viewing(
    body: ViewingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == body.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # A landlord can't request a viewing of their own listing.
    if listing.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot request a viewing of your own listing.")

    if not body.date or not body.time:
        raise HTTPException(status_code=400, detail="Please choose a date and time.")

    # Basic guard: don't allow dates in the past.
    try:
        chosen = datetime.strptime(f"{body.date} {body.time}", "%Y-%m-%d %H:%M")
        if chosen < datetime.now():
            raise HTTPException(status_code=400, detail="Please choose a future date and time.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format.")

    vr = ViewingRequest(
        listing_id=listing.id,
        student_id=current_user.id,
        landlord_id=listing.owner_id,
        preferred_date=body.date,
        preferred_time=body.time,
        notes=(body.notes or "").strip() or None,
        status="pending",
    )
    db.add(vr)
    db.commit()
    db.refresh(vr)
    return {"status": "success", "message": "Viewing requested. The landlord will confirm.", "request": _serialize(vr)}


# ── Student: my requests ──────────────────────────────────────────────────
@router.get("/mine")
def my_viewings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ViewingRequest)
        .filter(ViewingRequest.student_id == current_user.id)
        .order_by(ViewingRequest.created_at.desc())
        .all()
    )
    return [_serialize(v) for v in rows]


# ── Landlord: incoming requests ───────────────────────────────────────────
@router.get("/incoming")
def incoming_viewings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ViewingRequest)
        .filter(ViewingRequest.landlord_id == current_user.id)
        .order_by(ViewingRequest.created_at.desc())
        .all()
    )
    return [_serialize(v) for v in rows]


# ── Update status (landlord confirm/decline/complete; student cancel) ──────
@router.patch("/{viewing_id}")
def update_viewing(
    viewing_id: int,
    body: ViewingStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vr = db.query(ViewingRequest).filter(ViewingRequest.id == viewing_id).first()
    if not vr:
        raise HTTPException(status_code=404, detail="Viewing request not found.")

    new_status = (body.status or "").lower().strip()

    is_landlord = current_user.id == vr.landlord_id
    is_student = current_user.id == vr.student_id

    if is_landlord and new_status in LANDLORD_STATUSES:
        vr.status = new_status
    elif is_student and new_status in STUDENT_STATUSES:
        vr.status = new_status
    else:
        # Either not a party to this request, or not an allowed transition.
        raise HTTPException(status_code=403, detail="You can't make that change to this request.")

    db.commit()
    db.refresh(vr)
    return {"status": "success", "request": _serialize(vr)}
