from fastapi import APIRouter
from app.utils.response import success_response

router = APIRouter()

@router.get("/")
async def get_reviews():
    return success_response("Reviews fetched successfully", data=[])
