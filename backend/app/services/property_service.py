from sqlalchemy.orm import Session
from models.property import Property
from schemas.property import PropertyUpdate
from typing import List, Optional

def update_property(db: Session, property_id: int, update_data: PropertyUpdate, current_user: dict):
    # fetch property
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        return None
    #Permission check: owner or admin
    if current_user['role'] != 'admin' and prop.owner_id != current_user['id']:
        return "forbidden"
    #update fields
    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(prop, key, value)
    
    db.commit()
    db.refresh(prop)
    return prop

def delete_property(db: Session, property_id: int, current_user: dict):
    # Fetch the property
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        return None

    # Permission check: owner or admin
    if current_user['role'] != 'admin' and prop.owner_id != current_user['id']:
        return "forbidden"

    # Delete property
    db.delete(prop)
    db.commit()
    return "deleted"

def search_properties(
    db: Session,
    location: Optional[str] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 10,
    offset: int = 0
) -> List[Property]:
    query = db.query(Property)

    # Apply filters only if provided
    if location:
        query = query.filter(Property.location.ilike(f"%{location}%"))
    if property_type:
        query = query.filter(Property.property_type.ilike(f"%{property_type}%"))
    if min_price is not None:
        query = query.filter(Property.price >= min_price)
    if max_price is not None:
        query = query.filter(Property.price <= max_price)

    # Pagination
    query = query.limit(limit).offset(offset)

    return query.all()
