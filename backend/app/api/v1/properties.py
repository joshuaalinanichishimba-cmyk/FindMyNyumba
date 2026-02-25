from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import shutil
import os
from typing import List, Optional
from app.db.session import SessionLocal
from app.models.property import Property
from app.api.v1.auth import get_current_user, check_role

router = APIRouter()
UPLOAD_DIR = "static/property_images"

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.get("/")
def list_properties(db: Session = Depends(get_db), skip: int = 0, limit: int = 10):
    return db.query(Property).offset(skip).limit(limit).all()

@router.post("/")
def create_property(
    title: str, price: float, location: str, 
    db: Session = Depends(get_db), 
    # This is your Role Management in action:
    current_user = Depends(check_role("landlord"))
):
    new_prop = Property(title=title, price=price, location=location, owner_id=current_user.id)
    db.add(new_prop)
    db.commit()
    db.refresh(new_prop)
    return new_prop

@router.post("/{property_id}/upload-image")
async def upload_image(
    property_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop or prop.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this property")
    
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    file_path = os.path.join(UPLOAD_DIR, f"{property_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    prop.image_url = f"/static/property_images/{property_id}_{file.filename}"
    db.commit()
    return {"message": "Success", "url": prop.image_url}
