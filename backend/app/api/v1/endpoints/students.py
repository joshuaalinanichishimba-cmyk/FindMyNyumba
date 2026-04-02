from fastapi import APIRouter

router = APIRouter(prefix="/students", tags=["Student"])

@router.get("/dashboard/overview")
async def get_overview(): return {"status": "success", "data": {"saved_listings_count": 3, "active_inquiries_count": 1}}

@router.get("/saved-listings")
async def get_saved(): return {"status": "success", "data": []}

@router.get("/inquiries")
async def get_student_inquiries(): return {"status": "success", "data": []}
