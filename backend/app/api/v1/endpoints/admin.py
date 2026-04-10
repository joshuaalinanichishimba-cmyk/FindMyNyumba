from fastapi import APIRouter
router = APIRouter()

@router.get('/stats')
def stats(): return {'total_users': 0, 'total_listings': 0}