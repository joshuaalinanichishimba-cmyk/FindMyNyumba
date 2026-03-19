from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login/access-token")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/token")

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str

class TokenData(BaseModel):
    email: str | None = None

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user



# --- GOOGLE AUTHENTICATION ENDPOINT ---
@router.post("/google")
async def google_auth(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("credential")
    if not token:
        raise HTTPException(status_code=400, detail="Missing Google credential")
    
    # In a full production app, you would use google-auth library here:
    # idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)
    # email = idinfo['email']
    
    print(f"🎯 GOOGLE LOGIN ATTEMPT: Token received.")
    return {
        "access_token": "mock_google_jwt_for_testing", 
        "token_type": "bearer",
        "message": "Google Login Successful (Mock)"
    }

# --- GOOGLE AUTHENTICATION ENDPOINT ---
@router.post("/google")
async def google_auth(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("credential")
    if not token:
        raise HTTPException(status_code=400, detail="Missing Google credential")
    
    # In a full production app, you would use google-auth library here:
    # idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)
    # email = idinfo['email']
    
    print(f"🎯 GOOGLE LOGIN ATTEMPT: Token received.")
    return {
        "access_token": "mock_google_jwt_for_testing", 
        "token_type": "bearer",
        "message": "Google Login Successful (Mock)"
    }
