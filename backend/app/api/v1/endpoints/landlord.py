from fastapi import APIRouter
router = APIRouter()

@router.get('/properties')
def properties(): return {'message': 'Landlord active'}