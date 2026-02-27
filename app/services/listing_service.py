from sqlalchemy.orm import Session
from app.models.listing import Listing
from app.schemas.listing import ListingCreate

class ListingService:
    @staticmethod
    def create_new_listing(db: Session, listing_data: ListingCreate, landlord_id: int):
        db_listing = Listing(**listing_data.model_dump(), owner_id=landlord_id)
        db.add(db_listing)
        db.commit()
        db.refresh(db_listing)
        return db_listing

    @staticmethod
    def get_all_listings(db: Session, skip: int = 0, limit: int = 100, location: str = None, max_price: float = None):
        query = db.query(Listing)
        if location:
            query = query.filter(Listing.location.icontains(location))
        if max_price:
            query = query.filter(Listing.price <= max_price)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def get_user_listings(db: Session, user_id: int):
        return db.query(Listing).filter(Listing.owner_id == user_id).all()
