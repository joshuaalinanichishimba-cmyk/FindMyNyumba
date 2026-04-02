from pydantic import BaseModel
from typing import Optional

class ListingBase(BaseModel):
    title: str
    price: float
    location: str
    description: str

class ListingCreate(ListingBase):
    pass

class ListingResponse(ListingBase):
    id: int
    owner_id: int
    image_url: Optional[str] = None
    status: str
    is_boosted: bool

    class Config:
        from_attributes = True