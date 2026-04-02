"""
app/api/v1/endpoints/messages.py

FIXES:
- Dual-support for POST /messages/send: Now gracefully handles both JSON payloads 
  (from property.html) and FormData payloads (from messages.html). Fixes 422 error.
"""

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.listing import Listing
from app.models.message import Message
from app.models.user import User

router = APIRouter(prefix="/messages", tags=["Messages"])

ATTACH_DIR = Path("static/uploads/attachments")

# ── Unread count ──────────────────────────────────────────────────────────────
@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    count = db.query(Message).filter(
        Message.receiver_id == current_user.id,
        Message.is_read     == False,
    ).count()
    return {"unread_count": count}


# ── Conversations list ────────────────────────────────────────────────────────
@router.get("/conversations")
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
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

    seen    = {}
    threads = []

    for msg in all_msgs:
        other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        prop_id  = msg.property_id or 0
        key      = (other_id, prop_id)

        if key in seen:
            continue
        seen[key] = True

        other_user = db.query(User).filter(User.id == other_id).first()
        other_name = other_user.full_name if other_user else "Unknown"

        prop_title = None
        if prop_id:
            listing = db.query(Listing).filter(Listing.id == prop_id).first()
            if listing:
                prop_title = listing.title

        unread_count = db.query(Message).filter(
            Message.sender_id   == other_id,
            Message.receiver_id == current_user.id,
            Message.property_id == (prop_id if prop_id else None),
            Message.is_read     == False,
        ).count()

        threads.append({
            "other_user_id":   other_id,
            "other_user_name": other_name,
            "property_id":     prop_id,
            "property_title":  prop_title or "General Inquiry",
            "last_message":    msg.content,
            "unread_count":    unread_count,
        })

    return threads


# ── Thread (individual conversation) ─────────────────────────────────────────
@router.get("/thread/{property_id}/{other_user_id}")
def get_thread(
    property_id:   int,
    other_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
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

    for msg in msgs:
        if msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
    db.commit()

    result = []
    for msg in msgs:
        is_me = msg.sender_id == current_user.id
        result.append({
            "id":              msg.id,
            "content":         msg.content,
            "sender_name":     "Me" if is_me else (
                db.query(User).filter(User.id == msg.sender_id).first().full_name
                if db.query(User).filter(User.id == msg.sender_id).first() else "Unknown"
            ),
            "created_at":      msg.created_at.isoformat() if msg.created_at else None,
            "attachment_url":  None,   
            "attachment_name": None,
            "attachment_type": None,
        })

    return result


# ── Send message (Smart JSON/Form Handler) ────────────────────────────────────
@router.post("/send")
async def send_message(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    """
    Smart endpoint that checks the Content-Type. 
    Accepts both application/json (property pages) and multipart/form-data (messages dashboard).
    """
    content_type = request.headers.get("content-type", "")
    
    if "application/json" in content_type:
        data = await request.json()
        receiver_id = data.get("receiver_id")
        content     = data.get("content", "")
        prop_val    = data.get("property_id")
        property_id = int(prop_val) if prop_val else None
    else:
        form = await request.form()
        receiver_id = form.get("receiver_id")
        content     = form.get("content", "")
        prop_val    = form.get("property_id")
        property_id = int(prop_val) if prop_val and prop_val != "null" else None

    if not receiver_id:
        raise HTTPException(status_code=422, detail="receiver_id is required")

    receiver_id = int(receiver_id)

    if not content or not str(content).strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Recipient not found.")

    msg = Message(
        sender_id   = current_user.id,
        receiver_id = receiver_id,
        property_id = property_id,
        content     = str(content).strip(),
        is_read     = False,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    
    return {
        "status": "success", 
        "detail": "Message sent! The host will reply soon.", 
        "id": msg.id
    }
