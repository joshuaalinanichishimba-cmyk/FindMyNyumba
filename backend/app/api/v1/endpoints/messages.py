"""
app/api/v1/endpoints/messages.py

WHAT CHANGED IN THIS VERSION
----------------------------
- POST /messages/send now:
    (a) is rate limited (MESSAGE_SEND_LIMIT) to curb spam blasts, and
    (b) runs scam_detection.scan_message() on the outgoing text. If any signal
        fires (mobile-money number shared, "deposit before viewing", off-platform
        push, etc.) the message is STILL delivered, but an audit entry with
        action="message.scam_signal" is written so admins can review it via the
        existing GET /admin/audit endpoint. We flag rather than block so honest
        users aren't hit by false positives and so you collect real-world data
        before tightening.
- The N+1 fixes and dual JSON/FormData handling from the previous version are
  unchanged.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.audit import record_audit
from app.core.database import get_db
from app.core.rate_limiter import limiter, MESSAGE_SEND_LIMIT
from app.core.scam_detection import scan_message, risk_score
from app.models.listing import Listing
from app.models.message import Message
from app.models.user import User

router = APIRouter(prefix="/messages", tags=["Messages"])

ATTACH_DIR = Path("static/uploads/attachments")

ALLOWED_ATTACH_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_ATTACH_MB = 10


# ── Unread count ──────────────────────────────────────────────────────────
@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    count = db.query(Message).filter(
        Message.receiver_id == current_user.id,
        Message.is_read     == False,  # noqa: E712
    ).count()
    return {"unread_count": count}


# ── Conversations list ────────────────────────────────────────────────────────
@router.get("/conversations")
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    """
    Replaced per-thread unread COUNT queries with a single batch query.
    Old code: 1 + N queries (N = number of conversation threads).
    New code: 2 queries total regardless of thread count.
    """
    all_msgs = (
        db.query(Message)
        .filter(
            or_(
                Message.sender_id   == current_user.id,
                Message.receiver_id == current_user.id,
            )
        )
        .order_by(Message.created_at.desc())
        .all()
    )

    # Deduplicate: first (newest) message per (other_user, property) key
    seen    = {}
    threads = []

    for msg in all_msgs:
        other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        prop_id  = msg.property_id or 0
        key      = (other_id, prop_id)
        if key in seen:
            continue
        seen[key] = True
        threads.append((other_id, prop_id, msg))

    if not threads:
        return []

    other_ids   = {t[0] for t in threads}
    listing_ids = {t[1] for t in threads if t[1]}

    users    = {u.id: u for u in db.query(User).filter(User.id.in_(other_ids)).all()} if other_ids else {}
    listings = {l.id: l for l in db.query(Listing).filter(Listing.id.in_(listing_ids)).all()} if listing_ids else {}

    unread_rows = (
        db.query(
            Message.sender_id,
            Message.property_id,
            func.count(Message.id).label("cnt"),
        )
        .filter(
            Message.receiver_id == current_user.id,
            Message.is_read     == False,  # noqa: E712
            Message.sender_id.in_(other_ids),
        )
        .group_by(Message.sender_id, Message.property_id)
        .all()
    )
    unread_map = {(row.sender_id, row.property_id or 0): row.cnt for row in unread_rows}

    result = []
    for (other_id, prop_id, msg) in threads:
        other_user = users.get(other_id)
        listing    = listings.get(prop_id) if prop_id else None
        unread     = unread_map.get((other_id, prop_id), 0)
        result.append({
            "other_user_id":   other_id,
            "other_user_name": other_user.full_name if other_user else "Unknown",
            "property_id":     prop_id,
            "property_title":  listing.title if listing else "General Inquiry",
            "last_message":    msg.content,
            "unread_count":    unread,
        })

    return result


# ── Thread (individual conversation) ─────────────────────────────────────────
@router.get("/thread/{property_id}/{other_user_id}")
def get_thread(
    property_id:   int,
    other_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    """
    Eliminated N+1 query (other user pre-fetched once). Bulk mark-as-read.
    """
    prop_filter = (
        Message.property_id == property_id if property_id else Message.property_id.is_(None)
    )

    msgs = (
        db.query(Message)
        .filter(
            prop_filter,
            or_(
                and_(Message.sender_id == current_user.id,  Message.receiver_id == other_user_id),
                and_(Message.sender_id == other_user_id,    Message.receiver_id == current_user.id),
            ),
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    unread_ids = [m.id for m in msgs if m.receiver_id == current_user.id and not m.is_read]
    if unread_ids:
        db.query(Message).filter(Message.id.in_(unread_ids)).update(
            {"is_read": True}, synchronize_session=False
        )
        db.commit()

    other_user = db.query(User).filter(User.id == other_user_id).first()
    other_name = other_user.full_name if other_user else "Unknown"

    result = []
    for msg in msgs:
        is_me = msg.sender_id == current_user.id
        result.append({
            "id":              msg.id,
            "content":         msg.content,
            "is_mine":         is_me,
            "sender_name":     "Me" if is_me else other_name,
            "created_at":      msg.created_at.isoformat() if msg.created_at else None,
            "attachment_url":  msg.attachment_url,
            "attachment_name": msg.attachment_name,
            "attachment_type": msg.attachment_type,
        })

    return result


# ── Send message (Smart JSON/Form Handler) ────────────────────────────────────
@router.post("/send")
@limiter.limit(MESSAGE_SEND_LIMIT)
async def send_message(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    """
    Accepts both application/json (property detail page) and
    multipart/form-data (messages dashboard). Supports optional attachments.
    Runs a scam-signal scan and flags (does not block) suspicious messages.
    """
    content_type = request.headers.get("content-type", "")

    attachment_url  = None
    attachment_name = None
    attachment_type = None

    if "application/json" in content_type:
        data        = await request.json()
        receiver_id = data.get("receiver_id")
        content     = data.get("content", "")
        prop_val    = data.get("property_id")
        property_id = int(prop_val) if prop_val else None
    else:
        form        = await request.form()
        receiver_id = form.get("receiver_id")
        content     = form.get("content", "")
        prop_val    = form.get("property_id")
        property_id = int(prop_val) if prop_val and prop_val != "null" else None

        attachment_file = form.get("attachment")
        if attachment_file and hasattr(attachment_file, "filename") and attachment_file.filename:
            mime = attachment_file.content_type or "application/octet-stream"
            if mime not in ALLOWED_ATTACH_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file type. Allowed: images, PDF, Word docs, text files.",
                )
            ATTACH_DIR.mkdir(parents=True, exist_ok=True)
            safe_name  = f"{current_user.id}_{attachment_file.filename.replace(' ', '_')}"
            dest       = ATTACH_DIR / safe_name
            file_bytes = await attachment_file.read()
            if len(file_bytes) > MAX_ATTACH_MB * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"Attachment exceeds {MAX_ATTACH_MB}MB limit.")
            with open(dest, "wb") as f:
                f.write(file_bytes)
            attachment_url  = f"/static/uploads/attachments/{safe_name}"
            attachment_name = attachment_file.filename
            attachment_type = "image" if mime.startswith("image/") else "file"
            if not str(content).strip():
                content = f"[Attachment: {attachment_file.filename}]"

    if not receiver_id:
        raise HTTPException(status_code=422, detail="receiver_id is required")

    receiver_id = int(receiver_id)

    if not content or not str(content).strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Recipient not found.")

    clean_content = str(content).strip()

    msg = Message(
        sender_id       = current_user.id,
        receiver_id     = receiver_id,
        property_id     = property_id,
        content         = clean_content,
        is_read         = False,
        attachment_url  = attachment_url,
        attachment_name = attachment_name,
        attachment_type = attachment_type,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Anti-scam: scan the delivered text. Flag (don't block) so admins can review
    # via GET /admin/audit?action=message.scam_signal. False positives here are
    # cheap; a blocked legitimate message is not.
    signals = scan_message(clean_content)
    if signals:
        record_audit(
            db, request,
            actor=current_user,
            action="message.scam_signal",
            entity_type="message",
            entity_id=msg.id,
            meta={
                "signals": signals,
                "risk": risk_score(signals),
                "receiver_id": receiver_id,
                "property_id": property_id,
            },
        )

    return {
        "status":          "success",
        "detail":          "Message sent!",
        "id":              msg.id,
        "attachment_url":  attachment_url,
        "attachment_name": attachment_name,
        "attachment_type": attachment_type,
    }
