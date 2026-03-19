from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/stats")
def get_stats(db: Session = Depends(models.get_db)):
    return {
        "total_users": db.query(models.User).count(),
        "total_properties": db.query(models.Property).count(),
        "new_users_today": 0,
        "new_properties_today": 0
    }

@router.get("/users")
def get_users(db: Session = Depends(models.get_db)):
    users = db.query(models.User).all()
    return [{"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role} for u in users]

@router.get("/all-listings")
def get_listings(db: Session = Depends(models.get_db)):
    props = db.query(models.Property).all()
    return [{"id": p.id, "title": p.title, "location": p.location, "price": p.price} for p in props]

@router.get("/reports")
def get_reports():
    return [] # Placeholder to prevent 404 until you build a reporting system

@router.get("/verifications")
def get_verifications(db: Session = Depends(models.get_db)):
    pending = db.query(models.User).filter(
        models.User.role.in_(["landlord", "student_host"]),
        models.User.verification_status == "pending"
    ).all()
    return [{
        "id": u.id, "name": u.full_name, "email": u.email, 
        "role": u.role, "university": getattr(u, 'university', 'N/A'),
        "document_type": getattr(u, 'document_type', 'Document'), "status": u.verification_status
    } for u in pending]

@router.get("/analytics/growth")
def get_growth():
    return {"user_growth": [0,0,0,0,0,0], "top_locations": []}
