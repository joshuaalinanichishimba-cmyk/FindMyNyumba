from fastapi import APIRouter
router = APIRouter()

@router.get("/profile")
def get_profile():
    return {"message": "Student profile endpoint active"}