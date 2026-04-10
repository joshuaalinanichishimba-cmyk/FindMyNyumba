from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import auth, student, landlord, admin

app = FastAPI(title="FindMyNyumba")

# Keep the permissive CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "online"}

# 1. Bring the main routers back online!
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(student.router, prefix="/api/v1/student")
app.include_router(landlord.router, prefix="/api/v1/landlord")
app.include_router(admin.router, prefix="/api/v1/admin")

# 2. The missing endpoint your homepage is crying for
@app.get("/api/v1/properties")
def get_public_properties():
    # We return an empty list for now so the frontend "What Our Users Say" page stops crashing
    return [] 