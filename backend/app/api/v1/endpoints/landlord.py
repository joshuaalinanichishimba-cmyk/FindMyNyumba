from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.listing import Listing
from app.models.message import Message
from app.core.security import verify_password, get_password_hash
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil

router = APIRouter(prefix="/landlord", tags=["Landlord"])

@router.get("/dashboard/stats")
def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    active = db.query(Listing).filter(Listing.owner_id == current_user.id, Listing.status == "active").count()
    pending = db.query(Listing).filter(Listing.owner_id == current_user.id, Listing.status == "pending").count()
    unread = db.query(Message).filter(Message.receiver_id == current_user.id, Message.is_read == False).count()
    
    return {
        "active_listings": active,
        "pending_listings": pending,
        "total_views": active * 12, # Mocked metric
        "unread_inquiries": unread,
        "verification_status": "verified" if current_user.is_active else "unverified"
    }

@router.get("/properties")
def get_my_properties(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Listing).filter(Listing.owner_id == current_user.id).order_by(Listing.id.desc()).all()

@router.post("/properties")
def create_property(
    title: str = Form(...), price: float = Form(...), location: str = Form(...),
    description: str = Form(...), images: List[UploadFile] = File(None),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    image_url = None
    if images and len(images) > 0 and images[0].filename:
        # Save first image to static folder
        os.makedirs("static/uploads", exist_ok=True)
        file_path = f"static/uploads/{images[0].filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(images[0].file, buffer)
        image_url = f"http://127.0.0.1:8000/{file_path}"

    prop = Listing(title=title, price=price, location=location, description=description, owner_id=current_user.id, status="pending", image_url=image_url)
    db.add(prop)
    db.commit()
    return prop

@router.delete("/properties/{prop_id}")
def delete_property(prop_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prop = db.query(Listing).filter(Listing.id == prop_id, Listing.owner_id == current_user.id).first()
    if not prop: raise HTTPException(status_code=404, detail="Property not found")
    db.delete(prop)
    db.commit()
    return {"message": "Deleted successfully"}

@router.post("/properties/{prop_id}/boost")
def boost_property(prop_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prop = db.query(Listing).filter(Listing.id == prop_id, Listing.owner_id == current_user.id).first()
    if not prop: raise HTTPException(status_code=404, detail="Property not found")
    prop.is_boosted = True
    db.commit()
    return {"message": "Property boosted"}

@router.get("/inquiries")
def get_inquiries(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    messages = db.query(Message).filter(Message.receiver_id == current_user.id).order_by(Message.created_at.desc()).all()
    results = []
    for m in messages:
        sender = db.query(User).filter(User.id == m.sender_id).first()
        prop = db.query(Listing).filter(Listing.id == m.property_id).first() if m.property_id else None
        results.append({
            "id": m.id,
            "student_id": m.sender_id,
            "student_name": sender.full_name if sender else "Student",
            "property_id": m.property_id,
            "property": prop.title if prop else "General",
            "message": m.content,
            "is_read": m.is_read,
            "date": m.created_at.strftime("%b %d") if m.created_at else ""
        })
    return results

@router.get("/verification")
def get_verification(current_user: User = Depends(get_current_user)):
    return {"verification_status": "verified" if current_user.is_active else "unverified"}

@router.post("/verify")
def verify_account(doc1: UploadFile = File(...), doc2: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    return {"message": "Documents received and pending review"}

class ProfileUpdate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    business_name: Optional[str] = None

@router.put("/profile")
def update_profile(payload: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.full_name = payload.full_name
    if payload.phone: current_user.phone_number = payload.phone
    if payload.business_name: current_user.business_name = payload.business_name
    db.commit()
    return current_user

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

@router.post("/settings/password")
def update_password(payload: PasswordUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password updated"}

