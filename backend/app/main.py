from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Create FastAPI app
app = FastAPI(
    title="FindMyNyumba API",
    description="Student Housing Platform API",
    version="1.0.0"
)

# Configure CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://find-my-nyumba-original.vercel.app","https://nyumba-web.vercel.app","http://localhost:5500","http://127.0.0.1:5500","http://localhost:3000","http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic test endpoint
@app.get("/")
def root():
    return {"status": "online", "message": "FindMyNyumba API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

# Import and include routers
try:
    from app.api.v1.api import api_router
    app.include_router(api_router, prefix="/api/v1")
    print("✅ API router loaded successfully")
except Exception as e:
    print(f"⚠️ Could not load API router: {e}")

# Serve static files if directory exists
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
    print("✅ Static files mounted")
