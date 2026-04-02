from fastapi import APIRouter
from app.utils.response import success_response

router = APIRouter()

@router.get("/status")
async def get_status():
    return success_response("Admin system operational")
