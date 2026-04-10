from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import auth, student, landlord, admin
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="FindMyNyumba")

# CRITICAL: Allow your specific Vercel and Local URLs
origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "https://findmynyumba-web.vercel.app",
    "https://nyumba-web.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(student.router, prefix="/api/v1/student", tags=["Student"])
app.include_router(landlord.router, prefix="/api/v1/landlord", tags=["Landlord"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

@app.get("/")
def read_root():
    return {"status": "online", "message": "FindMyNyumba API is running"}