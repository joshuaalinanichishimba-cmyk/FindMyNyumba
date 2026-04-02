from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/properties")

class ReviewCreate(BaseModel): rating: int; comment: str
class ReportCreate(BaseModel): reason: str; description: Optional[str] = None

@router.get("")
@router.get("/")
async def get_all_properties():
    return [
        {"id": 1, "title": "House for Rent", "price": 1500, "location": "Near Campus", "image_url": "http://127.0.0.1:8000/static/uploads/properties/1_59ca72dd_House_foe_Rent.jpg", "is_boosted": False},
        {"id": 2, "title": "Servants quater", "price": 1300, "location": "Main Campus", "image_url": "http://127.0.0.1:8000/static/uploads/properties/2_19e354c3_Bh.jpg", "is_boosted": True}
    ]

@router.get("/{listing_id}")
async def get_listing_detail(listing_id: int):
    is_id_2 = (listing_id == 2)
    return {
        "id": listing_id,
        "title": "Servants quater" if is_id_2 else "House for Rent",
        "price": 1300 if is_id_2 else 1500,
        "location": "Main Campus" if is_id_2 else "Near Campus",
        "description": "Well-maintained living space.",
        "image_url": "http://127.0.0.1:8000/static/uploads/properties/2_19e354c3_Bh.jpg" if is_id_2 else "http://127.0.0.1:8000/static/uploads/properties/1_59ca72dd_House_foe_Rent.jpg",
        "is_boosted": is_id_2,
        "owner_id": 101,
        "owner": {"id": 101, "full_name": "Joy Nafukwe", "role": "student_host", "verification_status": "verified"}
    }

@router.post("/{listing_id}/reviews")
async def post_review(listing_id: int, review: ReviewCreate): return {"status": "success"}

@router.post("/{listing_id}/report")
async def report_property(listing_id: int, report: ReportCreate): return {"status": "success"}
