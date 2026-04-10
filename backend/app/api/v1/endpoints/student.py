from fastapi import APIRouter
router = APIRouter()

@router.get('/profile')
def profile(): return {'message': 'Student active'}