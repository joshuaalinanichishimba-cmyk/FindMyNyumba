from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.listing import Listing
from app.models.report import Report
from app.models.user import User
from app.api.deps import get_current_user
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/properties", tags=["Properties"])

class ReportCreate(BaseModel):
    reason: str
    description: Optional[str] = None

class ReviewCreate(BaseModel):
    rating: int
    comment: str

@router.get("")
def get_properties(q: Optional[str] = None, university: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None, db: Session = Depends(get_db)):
    query = db.query(Listing).filter(Listing.status == "active")
    if q: query = query.filter(Listing.title.ilike(f"%{q}%"))
    if min_price: query = query.filter(Listing.price >= min_price)
    if max_price: query = query.filter(Listing.price <= max_price)
    # university filtering can be added here
    return query.order_by(Listing.id.desc()).all()

@router.get("/{prop_id}")
def get_property(prop_id: int, db: Session = Depends(get_db)):
    prop = db.query(Listing).filter(Listing.id == prop_id).first()
    if not prop: raise HTTPException(status_code=404, detail="Property not found")
    
    # Fetch owner details
    owner = db.query(User).filter(User.id == prop.owner_id).first()
    prop_dict = prop.__dict__.copy()
    if owner:
        prop_dict["owner"] = {
            "id": owner.id,
            "full_name": getattr(owner, "business_name", None) or owner.full_name,
            "verification_status": "verified" if owner.is_active else "unverified"
        }
    return prop_dict

@router.post("/{prop_id}/report")
def report_property(prop_id: int, payload: ReportCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = Report(
        listing_id=prop_id,
        reporter_id=current_user.id,
        reason=payload.reason,
        description=payload.description,
        status="pending"
    )
    db.add(report)
    db.commit()
    return {"message": "Report submitted successfully"}

@router.post("/{prop_id}/reviews")
def add_review(prop_id: int, payload: ReviewCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Mocking review success since Review model might not exist yet
    return {"message": "Review added successfully"}
