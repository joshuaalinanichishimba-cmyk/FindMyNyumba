from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

router = APIRouter()

@router.post("/{property_id}")
async def post_review(property_id: int, content: str, db: Session = Depends(get_db)):
    return {"message": "Review added to property " + str(property_id)}
