import shutil
import os
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.core.database import engine, Base, get_db
from app.models import models
from app.schemas import schemas
import bcrypt
import jwt
import os
from datetime import datetime, timedelta

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-jwt-key")
ALGORITHM = "HS256"

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FindMyNyumba API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "FindMyNyumba API is running"}

@app.post("/api/auth/register")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), salt).decode('utf-8')
    
    db_user = models.User(email=user.email, hashed_password=hashed_password, role=user.role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User created successfully", "user_id": db_user.id}

class LoginRequest(schemas.BaseModel):
    email: schemas.EmailStr
    password: str

@app.post("/api/auth/login")
def login(user_credentials: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()
    if not user or not bcrypt.checkpw(user_credentials.password.encode('utf-8'), user.hashed_password.encode('utf-8')):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode = {"sub": user.email, "role": user.role, "exp": expire}
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "role": user.role}

@app.get("/api/properties", response_model=list[schemas.PropertyResponse])
def get_properties(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Property).offset(skip).limit(limit).all()

@app.post("/api/properties", response_model=schemas.PropertyResponse)
def create_property(property: schemas.PropertyCreate, db: Session = Depends(get_db)):
    db_property = models.Property(**property.model_dump())
    db.add(db_property)
    db.commit()
    db.refresh(db_property)
    return db_property



@app.delete("/api/properties/{property_id}")
async def delete_property(property_id: int, db: Session = Depends(get_db)):
    db_property = db.query(models.Property).filter(models.Property.id == property_id).first()
    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    db.delete(db_property)
    db.commit()
    return {"message": "Property deleted successfully"}



# --- DEDICATED IMAGE UPLOAD ROUTE ---
from fastapi import File, UploadFile, Form
import shutil
import uuid

@app.post("/api/properties_with_image")
async def create_property_with_image(
    title: str = Form(...),
    description: str = Form("No description provided"),
    price: float = Form(0.0),
    location: str = Form("Unknown Location"),
    landlord_id: int = Form(1),
    file: UploadFile = File(None),
    db = Depends(get_db)
):
    file_path = None
    if file and hasattr(file, 'filename') and file.filename:
        file_ext = file.filename.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = f"static/uploads/{unique_filename}"
        os.makedirs("static/uploads", exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    db_property = models.Property(
        title=title, description=description, price=price, 
        location=location, landlord_id=landlord_id, photo_url=file_path
    )
    db.add(db_property)
    db.commit()
    db.refresh(db_property)
    return db_property
