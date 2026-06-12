"""
app/api/v1/endpoints/admin_extra.py

ADDITIVE admin endpoints for the rebuilt admin dashboard. This router is
SEPARATE from your existing admin.py on purpose: it only defines routes that
admin.py does not already have, so there is no collision and nothing you have
working today is touched.

Routes use explicit full paths (no router prefix) so /notifications sits at
the API root while everything else lives under /admin. Register in
app/api/v1/api.py with:

    from app.api.v1.endpoints.admin_extra import router as admin_extra_router
    api_router.include_router(admin_extra_router)

Auth: every route requires role == "admin" via require_admin, mirroring your
require_student / require_landlord guards.

Honest-data rule (matches the frontend): endpoints return what genuinely
exists. New tables start empty, so their lists return [] and the dashboard
panels show clean "waiting" states rather than fabricated numbers.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.listing import Listing
from app.models.report import Report
from app.models.message import Message
from app.models.saved_listing import SavedListing
from app.models.listing_event import ListingEvent
from app.models.admin_models import (
    Transaction, Escrow, Institution, Notification, AuditLog, AdminNote,
    RolePermission,
)

router = APIRouter(tags=["Admin (extended)"])


# â”€â”€ Guards & helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


def _client_ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def write_audit(db: Session, request: Request, actor: User, action: str,
                entity_type: str | None = None, entity_id: str | int | None = None,
                meta: dict | None = None) -> None:
    """Append one immutable audit row. Best-effort: never blocks the action."""
    try:
        db.add(AuditLog(
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            meta=json.dumps(meta) if meta else None,
        ))
        db.commit()
    except Exception:
        db.rollback()


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def compute_risk(user: User, db: Session) -> tuple[int, str]:
    """
    Lightweight risk score 0..100 from data we already have. Lower = safer.
    Mirrors the blueprint formula, minus factors we don't model yet.
    """
    if not user:
        return 50, "medium"
    # Admins and staff are not risk-scored like landlords
    if getattr(user, "role", None) in ("admin", "super_admin", "verification_officer", "support_agent", "finance_officer", "content_moderator", "analytics_manager"):
        return 0, "low"
    score = 50
    score += -10 if user.phone_number else 10
    verified = (user.verification_status == "verified") or bool(user.is_verified)
    score += -15 if verified else 15
    score += -5 if (user.full_name and user.email) else 5

    listing_ids = [row[0] for row in
                   db.query(Listing.id).filter(Listing.owner_id == user.id).all()]
    if listing_ids:
        reports = (db.query(Report)
                   .filter(Report.listing_id.in_(listing_ids)).count())
        score += reports * 12

    score = max(0, min(100, score))
    band = "high" if score >= 67 else "medium" if score >= 34 else "low"
    return score, band


TXN_SOURCE_KEYS = ["verification_fee", "featured", "boost", "escrow_deposit", "viewing_fee"]

_VERIFY_DIR = Path("static/uploads/verification")


def _user_documents(user, request: Request, verification_status: str | None) -> list:
    """
    Surface a landlord/student-host's uploaded verification files.

    PRIMARY source = the persistent Cloudinary URLs stored on the user record
    (verification_doc1_url / verification_doc2_url) — the same source admin.py's
    verification queue uses. This is consistent across deploys.

    FALLBACK = the legacy on-disk pattern ({user_id}_doc1_* / {user_id}_doc2_*),
    used only if a Cloudinary URL is missing. Note Render wipes this directory on
    every deploy, so the fallback rarely yields anything in production — it exists
    only for local dev / legacy records.

    Returns the shape the listing/user detail document panel expects:
        [{ "doc_type": ..., "url": ..., "status": ... }, ...]
    Entries with no resolvable URL are omitted.

    `user` may be a User object or a bare user id (legacy callers); when only an
    id is passed, the Cloudinary lookup is skipped and we go straight to disk.
    """
    status_val = verification_status or "pending"

    # Allow being called with either the user object or just the id.
    user_obj = user if not isinstance(user, int) else None
    user_id = user.id if user_obj is not None else user

    docs = []
    mapping = [
        ("verification_doc1_url", "doc1", "nrc_front"),
        ("verification_doc2_url", "doc2", "ownership"),
    ]

    base = str(request.base_url).rstrip("/")
    dir_exists = _VERIFY_DIR.exists()

    for attr, tag, doc_type in mapping:
        url = getattr(user_obj, attr, None) if user_obj is not None else None

        # Fallback to scanning local disk only if no persistent URL exists.
        if not url and dir_exists:
            found = sorted(_VERIFY_DIR.glob(f"{user_id}_{tag}_*"))
            if found:
                url = f"{base}/static/uploads/verification/{found[-1].name}"

        if url:
            docs.append({
                "doc_type": doc_type,
                "url": url,
                "status": status_val,
            })

    return docs


def _listing_engagement(listing_id: int, db: Session) -> dict:
    """Real engagement: views from events, contacts from messages, saves from SavedListing."""
    views = db.query(ListingEvent).filter(
        ListingEvent.listing_id == listing_id, ListingEvent.kind == "view").count()
    try:
        contacts = (db.query(Message.sender_id)
                    .filter(Message.property_id == listing_id)
                    .distinct().count())
    except Exception:
        contacts = 0
    try:
        saves = db.query(SavedListing).filter(SavedListing.listing_id == listing_id).count()
    except Exception:
        saves = 0
    return {"views": views, "contacts": contacts, "saves": saves}


# â”€â”€ Request bodies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ReasonBody(BaseModel):
    reason: Optional[str] = None


class NoteBody(BaseModel):
    text: str


class InstitutionBody(BaseModel):
    name: str
    town: Optional[str] = None
    type: Optional[str] = None


class RbacBody(BaseModel):
    matrix: dict


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  LISTING DETAIL  (aggregates everything the slide-over renders)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/listings/{listing_id}")
def admin_listing_detail(listing_id: int, request: Request,
                         admin: User = Depends(require_admin),
                         db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    owner = db.query(User).filter(User.id == listing.owner_id).first()
    reports = (db.query(Report)
               .filter(Report.listing_id == listing_id)
               .order_by(Report.created_at.desc()).all())
    txns = (db.query(Transaction)
            .filter(Transaction.listing_id == listing_id)
            .order_by(Transaction.created_at.desc()).all())
    notes = (db.query(AdminNote)
             .filter(AdminNote.listing_id == listing_id)
             .order_by(AdminNote.created_at.desc()).all())
    audit = (db.query(AuditLog)
             .filter(AuditLog.entity_type == "listing",
                     AuditLog.entity_id == str(listing_id))
             .order_by(AuditLog.created_at.desc()).limit(20).all())

    note_authors = {}
    for n in notes:
        if n.author_id and n.author_id not in note_authors:
            u = db.query(User).filter(User.id == n.author_id).first()
            note_authors[n.author_id] = u.full_name if u else "admin"

    risk_score, risk_band = (compute_risk(owner, db) if owner else (None, None))
    engagement = _listing_engagement(listing_id, db)
    owner_docs = (_user_documents(owner, request, owner.verification_status)
                  if owner else [])

    return {
        "id": listing.id,
        "ref": f"FMN-{listing.id:06d}",
        "title": listing.title,
        "description": listing.description or "",
        "location": listing.location,
        "area": listing.location,
        "town": None,
        "price": listing.price,
        "listing_type": getattr(listing, "listing_type", None),
        "status": listing.status,
        "verification_status": (owner.verification_status if owner else None),
        "risk_score": risk_score,
        "risk_band": risk_band,
        "is_boosted": listing.is_boosted,
        "created_at": _iso(listing.created_at),
        "latitude": getattr(listing, "latitude", None),
        "longitude": getattr(listing, "longitude", None),
        "landlord": ({
            "id": owner.id, "full_name": owner.full_name, "email": owner.email,
            "phone": owner.phone_number, "nrc_number": owner.id_number,
            "nrc_status": owner.verification_status,
            "phone_verified": bool(owner.phone_number),
        } if owner else {}),
        "analytics": {
            "views": engagement["views"], "contacts": engagement["contacts"],
            "saves": engagement["saves"], "reports": len(reports),
            "conversion": (round(engagement["contacts"] / engagement["views"] * 100, 1)
                           if engagement["views"] else None),
        },
        "media": [
            {"url": m.media_url, "kind": m.media_type} for m in (listing.media or [])
        ],
        "documents": owner_docs,
        "timeline": [
            {"text": f"Listing created", "ts": _iso(listing.created_at), "kind": "create"},
        ],
        "reports": [
            {"id": r.id, "category": r.reason, "status": r.status,
             "reporter_name": (db.query(User).filter(User.id == r.reporter_id).first().full_name
                               if r.reporter_id else "user"),
             "created_at": _iso(r.created_at)} for r in reports
        ],
        "transactions": [
            {"ref": t.ref, "type": t.type, "amount": t.amount, "status": t.status,
             "method": t.method, "created_at": _iso(t.created_at)} for t in txns
        ],
        "notes": [
            {"text": n.text, "author": note_authors.get(n.author_id, "admin"),
             "created_at": _iso(n.created_at)} for n in notes
        ],
        "audit": [
            {"created_at": _iso(a.created_at), "actor": a.actor_role or "system",
             "action": a.action, "ip": a.ip_address} for a in audit
        ],
    }


@router.patch("/admin/listings/{listing_id}/suspend")
def admin_suspend_listing(listing_id: int, request: Request,
                          admin: User = Depends(require_admin),
                          db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    listing.status = "suspended"
    db.commit()
    write_audit(db, request, admin, "listing.suspend", "listing", listing_id)
    return {"status": "success"}


@router.patch("/admin/listings/{listing_id}/unsuspend")
def admin_unsuspend_listing(listing_id: int, request: Request,
                            admin: User = Depends(require_admin),
                            db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    listing.status = "active"
    db.commit()
    write_audit(db, request, admin, "listing.unsuspend", "listing", listing_id)
    return {"status": "success"}


@router.patch("/admin/listings/{listing_id}/hide")
def admin_hide_listing(listing_id: int, request: Request,
                       admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    listing.status = "hidden"
    db.commit()
    write_audit(db, request, admin, "listing.hide", "listing", listing_id)
    return {"status": "success"}


@router.post("/admin/listings/{listing_id}/notes", status_code=201)
def admin_add_note(listing_id: int, body: NoteBody, request: Request,
                   admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    if not db.query(Listing).filter(Listing.id == listing_id).first():
        raise HTTPException(status_code=404, detail="Listing not found.")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Note cannot be empty.")
    note = AdminNote(listing_id=listing_id, author_id=admin.id, text=text)
    db.add(note)
    db.commit()
    write_audit(db, request, admin, "listing.note", "listing", listing_id)
    return {"status": "success"}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  USER DETAIL  (drill into one student / landlord / staff member)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/users/{user_id}")
def admin_user_detail(user_id: int, request: Request,
                      admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found.")

    # Select only legacy columns so this endpoint works even if the
    # listing_type/lat/long migration hasn't run yet (avoids a 500).
    listing_rows = (db.query(Listing.id, Listing.title, Listing.status,
                             Listing.price, Listing.location)
                    .filter(Listing.owner_id == user_id).all())
    active = sum(1 for l in listing_rows if l.status == "active")
    suspended = sum(1 for l in listing_rows if l.status == "suspended")
    listing_ids = [l.id for l in listing_rows]
    reports_against = (db.query(Report).filter(Report.listing_id.in_(listing_ids)).count()
                       if listing_ids else 0)
    risk_score, risk_band = compute_risk(u, db)

    nrc_state = u.verification_status or "unverified"
    return {
        "id": u.id,
        "full_name": u.full_name,
        "email": u.email,
        "phone": u.phone_number,
        "role": u.role,
        "is_active": u.is_active,
        "status": "active" if u.is_active else "suspended",
        "avatar_url": u.avatar_url,
        "nrc_number": u.id_number,
        "business_name": u.business_name,
        "business_location": u.business_location,
        "verification_status": u.verification_status or "unverified",
        "verification_rejection_reason": u.verification_rejection_reason,
        "created_at": _iso(u.created_at),
        "last_login": _iso(u.last_login),
        "stats": {
            "listings": len(listing_rows),
            "active_listings": active,
            "suspended_listings": suspended,
            "reports_against": reports_against,
        },
        "verification": {
            "nrc": nrc_state,
            "phone": "verified" if u.phone_number else "unverified",
            "property": "verified" if (u.verification_status == "verified") else "unverified",
        },
        "risk_score": risk_score,
        "risk_band": risk_band,
        "documents": _user_documents(u, request, u.verification_status),
        "listings": [
            {"id": l.id, "title": l.title, "status": l.status,
             "price": l.price, "location": l.location} for l in listing_rows
        ],
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TRANSACTIONS  &  REVENUE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/transactions")
def admin_transactions(admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    rows = db.query(Transaction).order_by(Transaction.created_at.desc()).all()
    names = {}
    out = []
    for t in rows:
        if t.user_id not in names:
            u = db.query(User).filter(User.id == t.user_id).first()
            names[t.user_id] = u.full_name if u else f"User {t.user_id}"
        out.append({
            "id": t.id, "ref": t.ref, "user_id": t.user_id, "user_name": names[t.user_id],
            "listing_id": t.listing_id, "type": t.type, "amount": t.amount,
            "currency": t.currency, "method": t.method, "status": t.status,
            "created_at": _iso(t.created_at),
        })
    return out


@router.post("/admin/transactions/{txn_id}/refund")
def admin_refund(txn_id: int, body: ReasonBody, request: Request,
                 admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if t.status != "success":
        raise HTTPException(status_code=409, detail="Only successful transactions can be refunded.")
    t.status = "refunded"
    db.commit()
    write_audit(db, request, admin, "txn.refund", "transaction", txn_id,
                {"reason": body.reason})
    return {"status": "success"}


@router.get("/admin/revenue")
def admin_revenue(period: str = "monthly",
                  admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    txns = db.query(Transaction).filter(Transaction.status == "success").all()
    now = datetime.now(timezone.utc)
    today0 = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    month0 = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    year0 = datetime(now.year, 1, 1, tzinfo=timezone.utc)

    def _at(t):
        d = t.created_at
        if d and d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d

    today = sum(t.amount for t in txns if _at(t) and _at(t) >= today0)
    month = sum(t.amount for t in txns if _at(t) and _at(t) >= month0)
    year = sum(t.amount for t in txns if _at(t) and _at(t) >= year0)

    by_source = {k: 0.0 for k in TXN_SOURCE_KEYS}
    for t in txns:
        key = t.type if t.type in by_source else None
        if key == "escrow_deposit":
            by_source["escrow_deposit"] += t.amount
        elif key:
            by_source[key] += t.amount
    # map to the frontend's keys
    by_source_out = {
        "verification_fee": by_source["verification_fee"],
        "featured": by_source["featured"],
        "boost": by_source["boost"],
        "escrow": by_source["escrow_deposit"],
        "viewing": by_source["viewing_fee"],
    }

    # simple monthly trend for the current year
    labels, values = [], []
    for m in range(1, now.month + 1):
        start = datetime(now.year, m, 1, tzinfo=timezone.utc)
        end = datetime(now.year, m + 1, 1, tzinfo=timezone.utc) if m < 12 else datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        labels.append(start.strftime("%b"))
        values.append(sum(t.amount for t in txns if _at(t) and start <= _at(t) < end))

    return {
        "period": period,
        "today": today, "month": month, "year": year,
        "by_source": by_source_out,
        "trend": {"labels": labels, "values": values},
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  ESCROW
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/escrow")
def admin_escrow(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Escrow).order_by(Escrow.created_at.desc()).all()
    cache = {}

    def name(uid):
        if uid not in cache:
            u = db.query(User).filter(User.id == uid).first()
            cache[uid] = u.full_name if u else f"User {uid}"
        return cache[uid]

    return [{
        "id": e.id, "ref": e.ref or f"ESC-{e.id:06d}",
        "student_id": e.student_id, "student_name": name(e.student_id),
        "landlord_id": e.landlord_id, "landlord_name": name(e.landlord_id),
        "listing_id": e.listing_id, "amount": e.amount, "status": e.status,
    } for e in rows]


_ESCROW_TRANSITIONS = {
    "release": ("held", "released", "released_at"),
    "refund":  ("held", "refunded", "refunded_at"),
    "dispute": ("held", "disputed", None),
}


@router.post("/admin/escrow/{escrow_id}/{action}")
def admin_escrow_action(escrow_id: int, action: str, body: ReasonBody, request: Request,
                        admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)):
    if action not in _ESCROW_TRANSITIONS:
        raise HTTPException(status_code=400, detail="Unknown escrow action.")
    e = db.query(Escrow).filter(Escrow.id == escrow_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Escrow record not found.")
    required_from, new_status, ts_field = _ESCROW_TRANSITIONS[action]
    if e.status != required_from:
        raise HTTPException(status_code=409,
                            detail=f"Cannot {action} an escrow in '{e.status}' state.")
    e.status = new_status
    if ts_field:
        setattr(e, ts_field, datetime.now(timezone.utc))
    if action == "dispute":
        e.dispute_reason = body.reason
    db.commit()
    write_audit(db, request, admin, f"escrow.{action}", "escrow", escrow_id,
                {"reason": body.reason})
    return {"status": "success"}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  INSTITUTIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/institutions")
def admin_institutions(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Institution).order_by(Institution.name).all()
    return [{"id": i.id, "name": i.name, "town": i.town, "type": i.type,
             "student_count": None} for i in rows]


@router.post("/admin/institutions", status_code=201)
def admin_add_institution(body: InstitutionBody, request: Request,
                          admin: User = Depends(require_admin),
                          db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required.")
    inst = Institution(name=name, town=(body.town or "").strip() or None, type=body.type)
    db.add(inst)
    db.commit()
    write_audit(db, request, admin, "institution.create", "institution", inst.id)
    return {"status": "success", "id": inst.id}


@router.delete("/admin/institutions/{inst_id}")
def admin_delete_institution(inst_id: int, request: Request,
                             admin: User = Depends(require_admin),
                             db: Session = Depends(get_db)):
    inst = db.query(Institution).filter(Institution.id == inst_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")
    db.delete(inst)
    db.commit()
    write_audit(db, request, admin, "institution.delete", "institution", inst_id)
    return {"status": "success"}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  SUPPORT / CONVERSATIONS  (stubbed until Message schema is wired)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/conversations")
def admin_conversations(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Group the messages table into conversations (one per user-pair)."""
    msgs = db.query(Message).order_by(Message.created_at.desc()).all()
    name_cache, role_cache = {}, {}

    def info(uid):
        if uid not in name_cache:
            u = db.query(User).filter(User.id == uid).first()
            name_cache[uid] = (u.full_name if u else f"User {uid}")
            role_cache[uid] = (u.role if u else None)
        return name_cache[uid], role_cache[uid]

    convos: dict = {}
    for m in msgs:                       # newest-first, so first seen per pair is latest
        key = tuple(sorted([m.sender_id, m.receiver_id]))
        if key not in convos:
            a_name, a_role = info(key[0])
            b_name, b_role = info(key[1])
            roles = {a_role, b_role}
            if "admin" in roles:
                kind = "student_support"
            elif "student" in roles and ("landlord" in roles or "student_host" in roles):
                kind = "student_landlord"
            else:
                kind = "student_landlord"
            convos[key] = {
                "id": f"{key[0]}-{key[1]}",
                "kind": kind,
                "participant_name": f"{a_name} <-> {b_name}",
                "last_message": m.content,
                "last_at": m.created_at.strftime("%b %d") if m.created_at else "",
                "unread": 0,
            }
        if not m.is_read:
            convos[key]["unread"] += 1
    return list(convos.values())


def _msg_dict(m, admin_id):
    return {
        "id": m.id, "sender_id": m.sender_id, "receiver_id": m.receiver_id,
        "content": m.content, "is_read": m.is_read,
        "mine": (m.sender_id == admin_id),
        "created_at": _iso(m.created_at),
    }


@router.get("/admin/conversations/{conv_id}/messages")
def admin_conversation_thread(conv_id: str, admin: User = Depends(require_admin),
                              db: Session = Depends(get_db)):
    """Read a thread for a 'a-b' user pair (from the Support inbox)."""
    try:
        a, b = (int(x) for x in conv_id.split("-", 1))
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad conversation id.")
    msgs = (db.query(Message)
            .filter(((Message.sender_id == a) & (Message.receiver_id == b)) |
                    ((Message.sender_id == b) & (Message.receiver_id == a)))
            .order_by(Message.created_at.asc()).all())
    names = {}
    for uid in (a, b):
        u = db.query(User).filter(User.id == uid).first()
        names[uid] = u.full_name if u else f"User {uid}"
    return {"participants": names, "messages": [_msg_dict(m, admin.id) for m in msgs]}


@router.get("/admin/messages/{user_id}")
def admin_thread_with_user(user_id: int, admin: User = Depends(require_admin),
                           db: Session = Depends(get_db)):
    """The admin's own thread with one user (for the 'Message user' panel)."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found.")
    msgs = (db.query(Message)
            .filter(((Message.sender_id == admin.id) & (Message.receiver_id == user_id)) |
                    ((Message.sender_id == user_id) & (Message.receiver_id == admin.id)))
            .order_by(Message.created_at.asc()).all())
    # mark messages from the user as read
    for m in msgs:
        if m.receiver_id == admin.id and not m.is_read:
            m.is_read = True
    db.commit()
    return {"user": {"id": u.id, "full_name": u.full_name, "email": u.email},
            "messages": [_msg_dict(m, admin.id) for m in msgs]}


class SendMessageBody(BaseModel):
    receiver_id: int
    content: str


@router.post("/admin/messages", status_code=201)
def admin_send_message(body: SendMessageBody, request: Request,
                       admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    target = db.query(User).filter(User.id == body.receiver_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Recipient not found.")
    msg = Message(sender_id=admin.id, receiver_id=body.receiver_id,
                  content=content, is_read=False)
    db.add(msg)
    # notify the recipient in-app
    db.add(Notification(user_id=body.receiver_id, type="message",
                        title="Message from FindMyNyumba", body=content[:140]))
    db.commit()
    write_audit(db, request, admin, "message.send", "user", body.receiver_id)
    return {"status": "success", "id": msg.id}


@router.get("/admin/risk/landlords")
def admin_risk_landlords(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Computed risk for every landlord / student-host, highest first."""
    owners = (db.query(User)
              .filter(User.role.in_(["landlord", "student_host"])).all())
    out = []
    for u in owners:
        score, band = compute_risk(u, db)
        out.append({"id": u.id, "full_name": u.full_name, "email": u.email,
                    "risk_score": score, "risk_band": band})
    out.sort(key=lambda x: x["risk_score"], reverse=True)
    return out


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  ANALYTICS:  search demand + geo  (empty until search-event tracking exists)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/analytics/search")
def admin_analytics_search(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    # No search_events table yet â€” return empty so the panel is honest.
    return {"areas": []}


@router.get("/admin/analytics/geo")
def admin_analytics_geo(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"points": []}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  FRAUD SIGNALS  (real: computed from the users table)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/fraud/signals")
def admin_fraud_signals(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    def _dupes(col):
        rows = (db.query(col, func.count(User.id))
                .filter(col.isnot(None), col != "")
                .group_by(col).having(func.count(User.id) > 1).all())
        return sum(int(c) for _, c in rows)

    return {
        "duplicate_nrc": _dupes(User.id_number),
        "duplicate_phone": _dupes(User.phone_number),
        "multi_account": _dupes(User.id_number),  # same NRC across accounts
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  AUDIT LOG
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/admin/audit")
def admin_audit(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    cache = {}

    def actor_name(uid):
        if uid is None:
            return "system"
        if uid not in cache:
            u = db.query(User).filter(User.id == uid).first()
            cache[uid] = u.full_name if u else f"User {uid}"
        return cache[uid]

    return [{
        "id": a.id, "created_at": _iso(a.created_at), "actor": actor_name(a.actor_id),
        "role": a.actor_role, "action": a.action,
        "entity": f"{a.entity_type or ''}:{a.entity_id or ''}".strip(":"),
        "ip": a.ip_address,
    } for a in rows]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  RBAC  (role Ã— permission matrix)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
RBAC_DEFAULTS = {
    "super_admin": ["dashboard.view", "listing.moderate", "verification.review",
                    "user.moderate", "report.handle", "txn.view", "txn.refund",
                    "escrow.manage", "revenue.view", "analytics.view",
                    "broadcast.send", "audit.view", "rbac.manage"],
    "verification_officer": ["dashboard.view", "verification.review", "audit.view"],
    "support_agent": ["dashboard.view", "report.handle", "user.moderate",
                      "broadcast.send", "audit.view"],
    "finance_officer": ["dashboard.view", "txn.view", "txn.refund",
                        "escrow.manage", "revenue.view", "audit.view"],
    "content_moderator": ["dashboard.view", "listing.moderate", "user.moderate",
                          "report.handle", "audit.view"],
    "analytics_manager": ["dashboard.view", "revenue.view", "analytics.view",
                          "audit.view"],
}


@router.get("/admin/roles")
def admin_roles(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(RolePermission).all()
    if not rows:
        return {"matrix": RBAC_DEFAULTS}
    matrix: dict[str, list[str]] = {}
    for r in rows:
        matrix.setdefault(r.role, []).append(r.permission)
    return {"matrix": matrix}


@router.post("/admin/roles")
def admin_save_roles(body: RbacBody, request: Request,
                     admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    db.query(RolePermission).delete()
    for role, perms in (body.matrix or {}).items():
        for perm in perms:
            db.add(RolePermission(role=role, permission=perm))
    db.commit()
    write_audit(db, request, admin, "rbac.update", "roles", None)
    return {"status": "success"}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  NOTIFICATIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/notifications")
def my_notifications(current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    rows = (db.query(Notification)
            .filter((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)))
            .order_by(Notification.created_at.desc()).limit(50).all())
    return [{
        "id": n.id, "type": n.type, "title": n.title, "body": n.body,
        "read_at": _iso(n.read_at), "created_at": _iso(n.created_at),
    } for n in rows]


@router.patch("/notifications/{notif_id}/read")
def read_notification(notif_id: int, current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notif_id).first()
    if n and not n.read_at:
        n.read_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": "success"}


@router.patch("/notifications/read-all")
def read_all_notifications(current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    (db.query(Notification)
     .filter((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)),
             Notification.read_at.is_(None))
     .update({Notification.read_at: datetime.now(timezone.utc)}, synchronize_session=False))
    db.commit()
    return {"status": "success"}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  REPORT GENERATOR  (CSV now; xlsx/pdf return 501 until you add libs)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _csv_response(headers, rows, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/export/{filename}")
def admin_export(filename: str, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    if "." not in filename:
        raise HTTPException(status_code=400, detail="Use resource.format, e.g. transactions.csv")
    resource, fmt = filename.rsplit(".", 1)
    if fmt != "csv":
        raise HTTPException(status_code=501,
                            detail=f"{fmt.upper()} export not implemented yet â€” CSV is available.")

    if resource == "transactions":
        rows = [[t.ref, t.user_id, t.type, t.method, t.amount, t.status,
                 _iso(t.created_at)] for t in db.query(Transaction).all()]
        return _csv_response(["Ref", "User", "Type", "Method", "Amount", "Status", "Created"],
                             rows, "findmynyumba_transactions.csv")
    if resource == "users":
        rows = [[u.id, u.full_name, u.email, u.role, u.is_active]
                for u in db.query(User).all()]
        return _csv_response(["ID", "Name", "Email", "Role", "Active"],
                             rows, "findmynyumba_users.csv")
    if resource == "listings":
        rows = [[l.id, l.title, l.location, l.price, l.status]
                for l in db.query(Listing).all()]
        return _csv_response(["ID", "Title", "Location", "Price", "Status"],
                             rows, "findmynyumba_listings.csv")
    if resource == "revenue":
        rows = [[t.ref, t.type, t.amount, t.status, _iso(t.created_at)]
                for t in db.query(Transaction).filter(Transaction.status == "success").all()]
        return _csv_response(["Ref", "Type", "Amount", "Status", "Created"],
                             rows, "findmynyumba_revenue.csv")

    raise HTTPException(status_code=404, detail=f"Unknown export resource '{resource}'.")
