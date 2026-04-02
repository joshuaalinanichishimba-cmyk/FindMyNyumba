from fastapi import APIRouter
from app.utils.response import success_response

router = APIRouter()

@router.get("/")
async def get_properties():
    return success_response("Properties list fetched successfully", data=[])
