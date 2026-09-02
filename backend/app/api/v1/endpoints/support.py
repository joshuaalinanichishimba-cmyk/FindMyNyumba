"""
Support ticket endpoints.

POST /support/tickets            — public. Create a ticket, returns its public ticket_id.
GET  /support/tickets/{ticket_id}— public. Look up a ticket's current status.
GET  /admin/support/tickets      — admin. List tickets (optional status filter).
PATCH/admin/support/tickets/{id} — admin. Update status / add a resolution note.
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_admin
from app.models.support_ticket import SupportTicket
from app.models.user import User

router = APIRouter()

VALID_USER_TYPES = {"student", "landlord", "other"}
VALID_CATEGORIES = {"connect", "assist", "payment", "general"}
VALID_STATUSES   = {"new", "in_progress", "resolved", "closed"}


def _public(t: SupportTicket) -> dict:
    return {
        "ticket_id": t.ticket_id,
        "subject": t.subject,
        "category": t.category,
        "status": t.status,
        "resolution_note": t.resolution_note,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _admin(t: SupportTicket) -> dict:
    d = _public(t)
    d.update({
        "id": t.id,
        "user_type": t.user_type,
        "reference_id": t.reference_id,
        "message": t.message,
        "email": t.email,
    })
    return d


def _gen_ticket_id() -> str:
    return "FMN-T-" + secrets.token_hex(3).upper()


class TicketCreate(BaseModel):
    subject:      str = Field(..., min_length=3, max_length=160)
    message:      str = Field(..., min_length=5, max_length=4000)
    user_type:    Optional[str] = None
    category:     Optional[str] = None
    reference_id: Optional[str] = Field(None, max_length=120)
    email:        Optional[str] = Field(None, max_length=200)


@router.post("/support/tickets", status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    ut = (payload.user_type or "").strip().lower() or None
    if ut and ut not in VALID_USER_TYPES:
        raise HTTPException(status_code=400, detail="Invalid user type.")
    cat = (payload.category or "").strip().lower() or None
    if cat and cat not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category.")

    # generate a unique ticket_id
    tid = _gen_ticket_id()
    for _ in range(5):
        if not db.query(SupportTicket).filter(SupportTicket.ticket_id == tid).first():
            break
        tid = _gen_ticket_id()

    t = SupportTicket(
        ticket_id=tid,
        user_type=ut,
        category=cat,
        reference_id=(payload.reference_id or "").strip() or None,
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        email=(payload.email or "").strip() or None,
        status="new",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"ticket_id": t.ticket_id, "status": t.status,
            "message": "Your ticket has been submitted. Save your ticket ID to track it."}


@router.get("/support/tickets/{ticket_id}")
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    t = db.query(SupportTicket).filter(SupportTicket.ticket_id == ticket_id.strip().upper()).first()
    if not t:
        raise HTTPException(status_code=404, detail="No ticket found with that ID.")
    return _public(t)


@router.get("/admin/support/tickets")
def admin_list_tickets(status: Optional[str] = None,
                       admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    q = db.query(SupportTicket)
    if status and status in VALID_STATUSES:
        q = q.filter(SupportTicket.status == status)
    rows = q.order_by(SupportTicket.created_at.desc()).all()
    return {"count": len(rows), "tickets": [_admin(t) for t in rows]}


class TicketUpdate(BaseModel):
    status:          Optional[str] = None
    resolution_note: Optional[str] = None


@router.patch("/admin/support/tickets/{ticket_pk}")
def admin_update_ticket(ticket_pk: int, payload: TicketUpdate,
                        admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)):
    t = db.query(SupportTicket).filter(SupportTicket.id == ticket_pk).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    if payload.status is not None:
        s = payload.status.strip().lower()
        if s not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status.")
        t.status = s
    if payload.resolution_note is not None:
        t.resolution_note = payload.resolution_note.strip() or None
    db.commit()
    db.refresh(t)
    return _admin(t)
