from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.listing import ListingCreate, ListingResponse
from app.services.listing_service import ListingService
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter()

# STUDENT VIEW: Get all houses
@router.get("/", response_model=List[ListingResponse])
def read_listings(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    return ListingService.get_all_listings(db, skip=skip, limit=limit)

# LANDLORD: Create
@router.post("/", response_model=ListingResponse)
def create_listing(listing_in: ListingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return ListingService.create_new_listing(db, listing_in, current_user.id)

# LANDLORD: Update price or details
@router.put("/{listing_id}", response_model=ListingResponse)
def update_listing(listing_id: int, listing_in: ListingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    listing = ListingService.update_listing(db, listing_id, current_user.id, listing_in.model_dump())
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found or not authorized")
    return listing

# LANDLORD: Delete
@router.delete("/{listing_id}")
def delete_listing(listing_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = ListingService.delete_listing(db, listing_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"message": "Listing deleted successfully"}
