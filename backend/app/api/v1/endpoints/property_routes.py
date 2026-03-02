from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from schemas.property import PropertyUpdate
from services.property_service import update_property, delete_property, search_properties
from app.api.v1.auth import get_current_user  # your auth dependency
from typing import Optional

router = APIRouter(prefix="/properties", tags=["properties"])
@router.put("/{property_id}")
def update_listing(property_id: int, update_data: PropertyUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    result = update_property(db, property_id, update_data, current_user)
    
    if result is None:
        raise HTTPException(status_code=404, detail="Property not found")
    if result == "forbidden":
        raise HTTPException(status_code=403, detail="Not authorized to update this property")
    
    return {"status": "success", "data": result}

@router.delete("/{property_id}")
def delete_listing(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    result = delete_property(db, property_id, current_user)

    if result is None:
        raise HTTPException(status_code=404, detail="Property not found")
    if result == "forbidden":
        raise HTTPException(status_code=403, detail="Not authorized to delete this property")

    return {"status": "success", "message": "Property deleted successfully"}

@router.get("/search")
def search_listings(
    location: Optional[str] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    results = search_properties(
        db,
        location=location,
        property_type=property_type,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        offset=offset
    )

    return {"status": "success", "results_count": len(results), "data": results}