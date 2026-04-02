import shutil
from pathlib import Path
from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional, List

router = APIRouter(prefix="/landlord", tags=["Landlord"])

@router.get("/dashboard/stats")
async def get_stats(): return {"status": "success", "data": {"total_properties": 5, "active_inquiries": 12, "total_views": 340}}

@router.get("/properties")
async def get_properties(): return {"status": "success", "data": [{"id": 1, "title": "House for Rent", "price": 1500, "status": "Active"}]}

@router.post("/properties")
async def create_property(title: str = Form(...), price: float = Form(...), location: str = Form(...), description: str = Form(...), images: Optional[List[UploadFile]] = File(None)):
    print(f"🏠 Landlord created: {title}")
    if images:
        upload_dir = Path("static/uploads/properties")
        upload_dir.mkdir(parents=True, exist_ok=True)
        for img in images:
            with open(upload_dir / img.filename, "wb") as buffer: shutil.copyfileobj(img.file, buffer)
    return {"status": "success", "message": "Listed!"}

@router.get("/inquiries")
async def get_inquiries(): return {"status": "success", "data": []}

@router.get("/verification")
async def get_verification(): return {"status": "success", "data": {"status": "Verified"}}

@router.post("/verify")
async def submit_verification(): return {"status": "success", "message": "Verification submitted."}

@router.put("/profile")
async def update_profile(): return {"status": "success", "message": "Profile updated."}
