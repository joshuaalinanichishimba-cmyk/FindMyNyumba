from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.models.user import User
from app.models.listing import Listing
from app.models.saved_property import SavedProperty
from app.models.message import Message
import os, shutil

router = APIRouter(prefix="/api/v1/students", tags=["Student Dashboard"])

def get_current_user(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.role == "student").order_by(User.id.desc()).first()
    if not user: raise HTTPException(status_code=401, detail="No student found.")
    return user

# --- OVERVIEW & PROFILE ---
@router.get("/dashboard/overview")
async def get_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    saved_count = db.query(SavedProperty).filter(SavedProperty.user_id == current_user.id).count()
    recent = db.query(Listing).order_by(Listing.id.desc()).limit(6).all()
    return {
        "stats": {"saved_count": saved_count, "unread_messages_count": 0},
        "recent_properties": [{"id": p.id, "title": p.title, "price": f"KSH {p.price:,.0f}", "location": p.location, "status": "Active", "image_url": p.image_url} for p in recent]
    }

@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    return {"full_name": current_user.full_name, "email": current_user.email, "phone_number": current_user.phone_number or "", "avatar_url": current_user.avatar_url}

# FIXES THE 404 AVATAR ERROR
@router.get("/profile/avatar")
async def get_avatar(current_user: User = Depends(get_current_user)):
    default_avatar = f"https://ui-avatars.com/api/?name={current_user.full_name.replace(' ', '+')}&background=ea580c&color=fff"
    return {"avatar_url": current_user.avatar_url or default_avatar}

@router.put("/profile")
async def update_profile(payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.full_name = payload.get("full_name")
    current_user.phone_number = payload.get("phone_number")
    db.commit()
    return {"message": "Success"}

# --- SETTINGS ---
@router.get("/settings/preferences")
async def get_prefs(current_user: User = Depends(get_current_user)):
    return {"email_alerts": getattr(current_user, 'email_alerts', True), "sms_alerts": getattr(current_user, 'sms_alerts', False)}

@router.put("/settings/preferences")
async def update_prefs(payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.email_alerts = payload.get("email_alerts")
    current_user.sms_alerts = payload.get("sms_alerts")
    db.commit()
    return {"message": "Updated"}

class PasswordPayload(BaseModel):
    current_password: str
    new_password: str

@router.put("/settings/password")
async def update_password(payload: PasswordPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.hashed_password = payload.new_password
    db.commit()
    return {"message": "Password updated successfully"}

# --- REAL-TIME MESSAGING ---
@router.get("/conversations")
async def get_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get all users the student has chatted with
    messages = db.query(Message).filter(
        or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id)
    ).all()
    
    partner_ids = set([m.sender_id if m.sender_id != current_user.id else m.receiver_id for m in messages])
    
    convos = []
    for pid in partner_ids:
        partner = db.query(User).filter(User.id == pid).first()
        if partner:
            last_msg = db.query(Message).filter(
                or_(
                    and_(Message.sender_id == current_user.id, Message.receiver_id == pid),
                    and_(Message.sender_id == pid, Message.receiver_id == current_user.id)
                )
            ).order_by(Message.id.desc()).first()
            
            convos.append({
                "id": partner.id,
                "landlord_name": partner.full_name,
                "property_title": "Property Inquiry",
                "unread_count": 0,
                "last_message": last_msg.content if last_msg else ""
            })
    return convos

@router.get("/conversations/{chat_id}/messages")
async def get_messages(chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    messages = db.query(Message).filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == chat_id),
            and_(Message.sender_id == chat_id, Message.receiver_id == current_user.id)
        )
    ).order_by(Message.id.asc()).all()
    
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": "Me" if m.sender_id == current_user.id else "Landlord",
            "content": m.content,
            "created_at": m.created_at.isoformat()
        } for m in messages
    ]

class SendMessagePayload(BaseModel):
    content: str

@router.post("/conversations/{chat_id}/messages")
async def send_message(chat_id: int, payload: SendMessagePayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_msg = Message(sender_id=current_user.id, receiver_id=chat_id, content=payload.content)
    db.add(new_msg)
    db.commit()
    return {"message": "Sent", "content": payload.content}

@router.get("/saved-properties")
async def get_saved(current_user: User = Depends(get_current_user)): return []

# --- FILE UPLOAD ROUTE ---
import os
import shutil
from fastapi import UploadFile, File

@router.post("/conversations/{chat_id}/upload")
async def upload_file(chat_id: int, file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Save the file directly to the frontend's directory so it can be viewed easily
    upload_dir = os.path.join(os.getcwd(), "frontend", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Create the clickable file URL
    file_url = f"http://localhost:3000/uploads/{file.filename}"
    message_content = f"📎 Attachment: {file_url}"
    
    # Save as a message
    new_msg = Message(sender_id=current_user.id, receiver_id=chat_id, content=message_content)
    db.add(new_msg)
    db.commit()
    
    return {"message": "Uploaded", "content": message_content}
# --- REPORT ROUTE ---
from app.models.report import Report

class ReportPayload(BaseModel):
    target_id: Optional[int] = None
    reason: str

@router.post("/report")
async def submit_report(payload: ReportPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_report = Report(
        reporter_id=current_user.id,
        target_id=payload.target_id,
        reason=payload.reason
    )
    db.add(new_report)
    db.commit()
    return {"message": "Report submitted successfully"}

# --- PROFILE AVATAR UPLOAD ROUTE ---
@router.post("/profile/avatar")
async def upload_avatar(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Save the avatar to the frontend uploads folder
    upload_dir = os.path.join(os.getcwd(), "frontend", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Make the filename unique to prevent overwriting
    safe_filename = f"avatar_{current_user.id}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Update the user's database record with the new image URL
    avatar_url = f"http://localhost:3000/uploads/{safe_filename}"
    current_user.avatar_url = avatar_url
    db.commit()
    
    return {"message": "Avatar updated successfully", "avatar_url": avatar_url}