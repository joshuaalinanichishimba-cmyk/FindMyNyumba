from pydantic import BaseModel
from typing import Optional

class PropertyUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    location: Optional[str]
    property_type: Optional[str]
    price: Optional[float]
    
