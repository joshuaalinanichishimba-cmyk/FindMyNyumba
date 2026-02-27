from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.schemas.listing import ListingCreate, ListingResponse
from app.services.listing_service import ListingService
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[ListingResponse])
def read_listings(db: Session = Depends(get_db), location: Optional[str] = Query(None), max_price: Optional[float] = Query(None)):
    return ListingService.get_all_listings(db, location=location, max_price=max_price)

@router.get("/me", response_model=List[ListingResponse])
def read_my_listings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return ListingService.get_user_listings(db, current_user.id)

@router.post("/", response_model=ListingResponse)
def create_listing(listing_in: ListingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return ListingService.create_new_listing(db, listing_in, current_user.id)
