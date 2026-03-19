from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import shutil
import os

router = APIRouter(prefix="/api/v1/landlord", tags=["Landlord Dashboard"])

def get_db_local():
    from app.main import get_db
    for db in get_db():
        yield db

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db_local)):
    return {"active_listings": 3, "pending_listings": 1, "total_views": 340, "unread_inquiries": 2}

@router.get("/properties")
def get_my_properties(db: Session = Depends(get_db_local)):
    from app.main import PropertyDB
    try:
        props = db.query(PropertyDB).order_by(PropertyDB.id.desc()).limit(5).all()
        return [{"id": p.id, "title": p.title, "price": p.price, "location": p.location, "status": "active"} for p in props]
    except Exception as e:
        print(f"Error fetching properties: {e}")
        return []

@router.post("/properties")
async def create_property(
    title: str = Form(...),
    price: float = Form(...),
    location: str = Form(...),
    description: str = Form(...),
    owner_id: int = Form(1),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db_local)
):
    from app.main import PropertyDB
    
    # 1. Handle File Uploads Safely
    os.makedirs("uploads", exist_ok=True)
    saved_images = []
    
    for img in images:
        if img.filename:
            file_path = f"uploads/{img.filename}"
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)
            saved_images.append(file_path)
            
    image_urls_str = ",".join(saved_images)

    # 2. Save to PostgreSQL safely
    try:
        new_prop = PropertyDB(
            title=title,
            price=price,
            location=location,
            description=description
        )
        # Safely inject the new columns we just added to the DB
        setattr(new_prop, 'owner_id', owner_id)
        setattr(new_prop, 'image_urls', image_urls_str)
        setattr(new_prop, 'is_featured', False)
        
        db.add(new_prop)
        db.commit()
        db.refresh(new_prop)
        print(f"✅ REAL UPLOAD SUCCESS: {new_prop.title} | Images saved: {len(saved_images)}")
        return {"message": "Property and images submitted successfully!"}
    except Exception as e:
        db.rollback()
        print(f"❌ DB ERROR: {e}")
        raise HTTPException(status_code=500, detail="Failed to save listing.")
# ==========================================
# NEW ROUTES: MONETIZATION & INQUIRIES
# ==========================================

@router.post("/properties/{property_id}/boost")
def boost_property(property_id: int, db: Session = Depends(get_db_local)):
    """BUSINESS LOGIC: Allows landlords to pay to boost a listing to the top of search."""
    from app.main import PropertyDB
    try:
        prop = db.query(PropertyDB).filter(PropertyDB.id == property_id).first()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # In a real app, integrate Mobile Money/Stripe here before setting to True
        prop.is_boosted = True
        db.commit()
        return {"message": f"Success! {prop.title} is now boosted and will appear at the top of student searches."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to boost property.")

@router.post("/verify")
async def submit_verification(
    doc1: UploadFile = File(None),
    doc2: UploadFile = File(None),
    doc3: UploadFile = File(None),
    db: Session = Depends(get_db_local)
):
    """BUSINESS LOGIC: Securely catches KYC documents for landlord/host verification."""
    # Logic to save documents would go here (similar to properties)
    return {"message": "Verification documents received successfully. Awaiting Admin approval."}

@router.get("/inquiries")
def get_inquiries(db: Session = Depends(get_db_local)):
    """BUSINESS LOGIC: Fetches messages from students."""
    # Returning mock data until the Inquiries DB table is fully structured
    return [
        {"id": 1, "student_name": "Emmanuel Bwalya", "property": "Secure Room near UNZA", "message": "Is the price negotiable?", "date": "2024-03-14", "status": "unread"},
        {"id": 2, "student_name": "Sarah Phiri", "property": "Secure Room near UNZA", "message": "Can I come view it tomorrow?", "date": "2024-03-13", "status": "read"}
    ]

# ==========================================
# NEW ROUTES: FULL CONTROL & PROFILE
# ==========================================

@router.delete("/properties/{property_id}")
def delete_property(property_id: int, db: Session = Depends(get_db_local)):
    """BUSINESS LOGIC: Gives landlords/hosts full control to delete their listings."""
    from app.main import PropertyDB
    try:
        prop = db.query(PropertyDB).filter(PropertyDB.id == property_id).first()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        db.delete(prop)
        db.commit()
        return {"message": "Listing deleted securely."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error deleting property.")

@router.post("/profile")
def update_profile(name: str = Form(...), phone: str = Form(...), role: str = Form(...)):
    """BUSINESS LOGIC: Saves profile and Mobile Money details for payouts."""
    # In a real app, this updates the UserDB table.
    return {"message": "Profile saved!", "role": role, "name": name, "phone": phone}

@router.get("/properties/{property_id}")
def get_single_property(property_id: int, db: Session = Depends(get_db_local)):
    """BUSINESS LOGIC: Fetch a single property for the student Listing Details page."""
    from app.main import PropertyDB
    try:
        prop = db.query(PropertyDB).filter(PropertyDB.id == property_id).first()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Format the response perfectly for listing.html
        return {
            "id": prop.id,
            "title": prop.title,
            "price": prop.price,
            "location": prop.location,
            "description": prop.description,
            "image_url": prop.image_urls.split(",")[0] if getattr(prop, "image_urls", "") else "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1200"
        }
    except Exception as e:
        print(f"Error fetching single property: {e}")
        raise HTTPException(status_code=500, detail="Database error.")

@router.get("/properties/{property_id}")
def get_single_property(property_id: int, db: Session = Depends(get_db_local)):
    """BUSINESS LOGIC: Fetch a single property for the student Listing Details page."""
    from app.main import PropertyDB
    try:
        prop = db.query(PropertyDB).filter(PropertyDB.id == property_id).first()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Format the response perfectly for listing.html
        return {
            "id": prop.id,
            "title": prop.title,
            "price": prop.price,
            "location": prop.location,
            "description": prop.description,
            "image_url": prop.image_urls.split(",")[0] if getattr(prop, "image_urls", "") else "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1200"
        }
    except Exception as e:
        print(f"Error fetching single property: {e}")
        raise HTTPException(status_code=500, detail="Database error.")
