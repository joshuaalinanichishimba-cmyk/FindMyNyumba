from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.database import engine, Base

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FindMyNyumba API", version="1.0.0")

# Allow your Frontend to talk to the Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect all the routes (Auth, Properties, Admin)
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "online", "message": "FindMyNyumba Backend is Core Correct"}
