from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.v1.router import api_router
from app.db.session import SessionLocal
from app.models.property import Property
import os

app = FastAPI(title="FindMyNyumba API")
templates = Jinja2Templates(directory="templates")

if not os.path.exists("static/property_images"):
    os.makedirs("static/property_images")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def home_gallery(request: Request):
    db = SessionLocal()
    properties = db.query(Property).all()
    db.close()
    return templates.TemplateResponse("gallery.html", {"request": request, "properties": properties})

app.include_router(api_router, prefix="/api/v1")
