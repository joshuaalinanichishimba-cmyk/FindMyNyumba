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
    def get_all_listings(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Listing).offset(skip).limit(limit).all()

    @staticmethod
    def update_listing(db: Session, listing_id: int, landlord_id: int, update_data: dict):
        db_listing = db.query(Listing).filter(Listing.id == listing_id, Listing.owner_id == landlord_id).first()
        if not db_listing:
            return None
        for key, value in update_data.items():
            setattr(db_listing, key, value)
        db.commit()
        db.refresh(db_listing)
        return db_listing

    @staticmethod
    def delete_listing(db: Session, listing_id: int, landlord_id: int):
        db_listing = db.query(Listing).filter(Listing.id == listing_id, Listing.owner_id == landlord_id).first()
        if db_listing:
            db.delete(db_listing)
            db.commit()
            return True
        return False
