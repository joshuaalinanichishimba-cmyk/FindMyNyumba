from app.core.database import engine, Base
from sqlalchemy import Boolean
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from fastapi import Depends
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


DATABASE_URL = "postgresql://postgres:12345@localhost:5432/findmynyumba"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Database Models ---
class ReviewDB(Base):
    __tablename__ = "reviews"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, index=True)
    student_name = Column(String)
    rating = Column(Integer)
    comment = Column(Text)

class NotificationDB(Base):
    __tablename__ = "notifications"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String) # 'student' or 'landlord'
    user_id = Column(Integer)
    message = Column(String)
    is_read = Column(Boolean, default=False)

class PropertyDB(Base):
    __tablename__ = "properties"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    price = Column(Float)
    location = Column(String)
    description = Column(Text)



# Create all tables on startup
Base.metadata.create_all(bind=engine)
app = FastAPI()

# --- CORS SETTINGS ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from . import admin_router
app.include_router(admin_router.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, Form, File, UploadFile
from typing import List


class PropertyCreate(BaseModel):
    title: str
    location: str
    price: float
    rooms: int
    status: str
    description: str

@app.post("/api/v1/properties")
async def create_property(
    title: str = Form(...),
    location: str = Form(...),
    price: float = Form(...),
    rooms: int = Form(...),
    description: str = Form(...),
    status: str = Form("Active"),
    images: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    # Create the DB entry
    db_property = PropertyDB(
        title=title, 
        location=location, 
        price=price, 
        rooms=rooms, 
        description=description, 
        status=status
    )
    db.add(db_property)
    db.commit()
    db.refresh(db_property)
    
    # Handle image saving logic here if needed (omitted for brevity)
# --- GOOGLE LOGIN ENDPOINT ---
@app.post('/api/v1/auth/google-login')
def google_login_endpoint(payload: dict):
    print('\n============================================================\n🌐 GOOGLE SIGN-IN SUCCESS!\n============================================================\n')
    return {'access_token': 'google_mock_token_456', 'token_type': 'bearer', 'role': 'student'}

from app.landlord_router import router as landlord_r
app.include_router(landlord_r)


# =========================================================
# STANDARD AUTHENTICATION ENDPOINTS (LOGIN & REGISTER)
# =========================================================
class RegisterPayload(BaseModel):
    full_name: str = None
    email: str
    password: str
    role: str
    phone_number: str = None

@app.post('/api/v1/auth/register')
def register_endpoint(payload: RegisterPayload):
    print(f'\n============================================================')
    print(f'✅ NEW REGISTRATION: {payload.email} as a {payload.role.upper()}')
    print(f'============================================================\n')
    # Later you can add db.add(UserDB(...)) here!
    return {'message': 'User created successfully', 'role': payload.role}


class LoginPayload(BaseModel):
    email: str
    password: str

@app.post('/api/v1/auth/login')
def login_endpoint(payload: LoginPayload):
    print(f'\n============================================================')
    print(f'🔓 USER LOGGED IN: {payload.email}')
    print(f'============================================================\n')
    
    # Smart routing for testing!
    if 'landlord' in payload.email.lower():
        role = 'landlord'
    elif 'host' in payload.email.lower():
        role = 'student_host'
    else:
        role = 'student'
    
    return {
        'access_token': 'mock_auth_token_789', 
        'token_type': 'bearer', 
        'role': role
    }

# Injecting Student Dashboard API Routes
from app.student_endpoints import router as student_router
app.include_router(student_router)
