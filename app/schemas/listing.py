from pydantic import BaseModel
from typing import Optional

class ListingBase(BaseModel):
    title: str
    description: str
    price: float
    location: str
    image_url: Optional[str] = None

class ListingCreate(ListingBase):
    pass

class ListingResponse(ListingBase):
    id: int
    owner_id: int
    class Config:
        from_attributes = True
