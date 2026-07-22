"""
app/api/v1/endpoints/messages.py
Shared messaging engine â€” works for all authenticated roles.
"""
import os
import shutil
import time
from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.user import User
from app.models.message import Message


def _has_paid_access(db, user_id) -> bool:
    """True if user has a successful verification/tier payment in the last 30 days."""
    if not user_id:
        return False
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    from app.models.admin_models import Transaction
    cutoff = _dt.now(_tz.utc) - _td(days=30)
    return db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.type == "verification_fee",
        Transaction.status == "success",
        Transaction.created_at >= cutoff,
    ).first() is not None
from app.models.listing import Listing

from slowapi import Limiter
from slowapi.util import get_remote_address

# FIX: removed broken `from app.schemas.message import MessageResponse` import
# that was imported but never used and would crash the app if the schema file
# didn't exist.

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/messages", tags=["Messaging Engine"])


# â”€â”€ Send Message â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.post("/send")
@limiter.limit("20/minute")
async def send_message(
    request: Request,
    receiver_id: int = Form(...),
    property_id: Optional[int] = Form(None),
    content: str = Form(...),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id == receiver_id:
        raise HTTPException(status_code=400, detail="You cannot message yourself.")
    # Messaging paywall (toggle-gated). Students need paid access; landlords reply free.
    if (settings.PAYWALL_ENABLED
            and getattr(current_user, "role", "") == "student"
            and not _has_paid_access(db, current_user.id)):
        raise HTTPException(
            status_code=403,
            detail="Verified Access required. Get Verified Access to message landlords.",
        )

    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found.")

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty.")

    attachment_url = attachment_name = attachment_type = None

    if attachment and attachment.filename:
        upload_dir = os.path.join(os.getcwd(), "static", "uploads", "messages")
        os.makedirs(upload_dir, exist_ok=True)
        safe_name = f"{current_user.id}_{int(time.time())}_{attachment.filename.replace(' ', '_')}"
        file_path = os.path.join(upload_dir, safe_name)
        contents = await attachment.read()
        with open(file_path, "wb") as buf:
            buf.write(contents)
        # FIX: use settings.BACKEND_URL instead of hardcoded 127.0.0.1
        attachment_url  = f"{settings.BACKEND_URL}/static/uploads/messages/{safe_name}"
        attachment_name = attachment.filename
        attachment_type = attachment.content_type

    new_msg = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        property_id=property_id,
        content=content.strip(),
        attachment_url=attachment_url,
        attachment_name=attachment_name,
        attachment_type=attachment_type,
        is_read=False,
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    return {"message": "Message sent successfully!", "id": new_msg.id}


# â”€â”€ Conversations List â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/conversations")
def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    all_msgs = (
        db.query(Message)
        .filter(or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id))
        .order_by(desc(Message.created_at))
        .all()
    )

    # Pre-fetch all relevant user IDs and listing IDs to avoid N+1 queries
    other_ids   = {(m.receiver_id if m.sender_id == current_user.id else m.sender_id) for m in all_msgs}
    prop_ids    = {m.property_id for m in all_msgs if m.property_id}

    users_map    = {u.id: u for u in db.query(User).filter(User.id.in_(other_ids)).all()}
    listings_map = {l.id: l for l in db.query(Listing).filter(Listing.id.in_(prop_ids)).all()} if prop_ids else {}

    conversations = {}
    for msg in all_msgs:
        other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        prop_id  = msg.property_id  # keep as None if None â€” do not coerce to 0

        # FIX: use actual None as part of key, not 0, to avoid thread mismatch bug
        thread_key = f"{other_id}_{prop_id}"

        if thread_key not in conversations:
            other_user = users_map.get(other_id)
            prop       = listings_map.get(prop_id) if prop_id else None

            conversations[thread_key] = {
                "property_id": prop_id,       # None if no property
                "property_title": prop.title if prop else "General Inquiry",
                "other_user_id": other_id,
                "other_user_name": other_user.full_name if other_user else "Unknown User",
                "last_message": msg.content,
                "last_message_time": msg.created_at,
                "unread_count": 0,
            }

        if msg.receiver_id == current_user.id and not msg.is_read:
            conversations[thread_key]["unread_count"] += 1

    return list(conversations.values())


# â”€â”€ Thread (with mark-as-read) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/thread/{property_id}/{other_user_id}")
def get_thread(
    property_id: int,
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # FIX: property_id == 0 means "no property" â€” filter on IS NULL, not == 0
    prop_filter = (
        Message.property_id == property_id
        if property_id != 0
        else Message.property_id.is_(None)
    )

    thread_msgs = (
        db.query(Message)
        .filter(
            prop_filter,
            or_(
                and_(Message.sender_id == current_user.id, Message.receiver_id == other_user_id),
                and_(Message.sender_id == other_user_id, Message.receiver_id == current_user.id),
            ),
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    # Mark received messages in this thread as read
    unread = [m for m in thread_msgs if m.receiver_id == current_user.id and not m.is_read]
    for m in unread:
        m.is_read = True
    if unread:
        db.commit()

    other_user = db.query(User).filter(User.id == other_user_id).first()
    other_name = other_user.full_name if other_user else "User"

    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "sender_name": "Me" if m.sender_id == current_user.id else other_name,
            "content": m.content,
            "is_read": m.is_read,
            "created_at": m.created_at,
            "attachment_url": getattr(m, "attachment_url", None),
            "attachment_name": getattr(m, "attachment_name", None),
            "attachment_type": getattr(m, "attachment_type", None),
        }
        for m in thread_msgs
    ]


# â”€â”€ Unread Count â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.get("/unread-count")
def get_unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    count = db.query(Message).filter(
        Message.receiver_id == current_user.id,
        Message.is_read == False
    ).count()
    return {"unread_count": count}
