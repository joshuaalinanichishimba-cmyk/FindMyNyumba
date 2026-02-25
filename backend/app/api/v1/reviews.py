from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.db.session import SessionLocal
from app.models.review import Review
from app.models.property import Property
from app.api.v1.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.get("/{property_id}")
def get_property_reviews(property_id: int, db: Session = Depends(get_db)):
    """Get all reviews for a property — call this as /api/v1/reviews/{property_id}"""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    reviews = db.query(Review).filter(Review.property_id == property_id).all()
    return {
        "property_id": property_id,
        "reviews": reviews
    }

@router.get("/{property_id}/summary")
def get_property_rating_summary(property_id: int, db: Session = Depends(get_db)):
    """Get average rating summary — call this as /api/v1/reviews/{property_id}/summary"""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return {
        "property_id": property_id,
        "average_rating": prop.average_rating,
        "total_reviews": len(prop.reviews)
    }

@router.post("/{property_id}")
def create_review(
    property_id: int,
    rating: int,
    comment: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Leave a review on a property — requires login"""
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    review = Review(
        property_id=property_id,
        user_id=current_user.id,
        rating=rating,
        comment=comment
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return {"message": "Review submitted", "review": review}
