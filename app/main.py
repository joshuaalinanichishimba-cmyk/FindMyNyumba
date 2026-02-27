from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
import os

app = FastAPI(title="FindMyNyumba API")

# Create directory if it doesn't exist (safety check)
if not os.path.exists("static/uploads"):
    os.makedirs("static/uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# This line is the magic - it makes images accessible via URL
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to FindMyNyumba API"}
