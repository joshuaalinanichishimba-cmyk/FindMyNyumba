from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, status
from . import models, schemas

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "YOUR_SUPER_SECRET_KEY" # In production, use environment variables
ALGORITHM = "HS256"

# 1. Login Logic
@router.post("/login")
def login(payload: schemas.UserLogin, db: Session = Depends(models.get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not pwd_context.verify(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = jwt.encode({"sub": user.email, "role": user.role}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

# 2. Forgot Password - Generate Token
@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(models.get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    # Security: Always return success to prevent user enumeration
    if user:
        reset_token = jwt.encode({"exp": datetime.utcnow() + timedelta(minutes=20), "sub": user.email}, SECRET_KEY, algorithm=ALGORITHM)
        # In a real app, you would send reset_token via email here
        print(f"DEBUG: Reset Link: http://localhost:3000/reset-password.html?token={reset_token}")
    
    return {"message": "If this email exists, a reset link has been sent."}

# 3. Reset Password - Verify and Update
@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordSubmit, db: Session = Depends(models.get_db)):
    try:
        payload_data = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload_data.get("sub")
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user: raise HTTPException(status_code=400, detail="Invalid token")
        
        user.hashed_password = pwd_context.hash(payload.new_password)
        db.commit()
        return {"message": "Password updated successfully"}
    except JWTError:
        raise HTTPException(status_code=400, detail="Reset link expired or invalid")

from google.oauth2 import id_token
from google.auth.transport import requests

GOOGLE_CLIENT_ID = "194165956778-jb953iejb3mnubcnlq40c8u00n0bo4mt.apps.googleusercontent.com"

@router.post("/google-login")
def google_login(payload: dict, db: Session = Depends(models.get_db)):
    token = payload.get("credential")
    try:
        # 1. Verify the token with Google
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        
        email = idinfo['email']
        full_name = idinfo.get('name', 'Google User')
        
        # 2. Check if user exists, otherwise create them
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            user = models.User(
                email=email,
                full_name=full_name,
                role="student", # Default role for Google sign-ups
                is_verified=True,
                hashed_password="GOOGLE_AUTH_EXTERNAL" 
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 3. Create access token
        access_token = jwt.encode({"sub": user.email, "role": user.role}, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": access_token, "token_type": "bearer", "role": user.role}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Google token")
