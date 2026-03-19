from . import admin_router
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.errors import setup_exception_handlers
from app.core.rate_limiter import setup_rate_limiting
from app.api.v1.endpoints import uploads, listings, students, auth

app = FastAPI(title="FindMyNyumba API", version="1.0.0")
app.include_router(admin_router.router)

setup_exception_handlers(app)
setup_rate_limiting(app)

app.mount("/static", StaticFiles(directory="uploads/images"), name="static")

app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(uploads.router, prefix="/api/v1", tags=["Uploads"])
app.include_router(listings.router, prefix="/api/v1", tags=["Listings"])
app.include_router(students.router, prefix="/api/v1", tags=["Students"])

@app.get("/")
async def root():
    return {"message": "FindMyNyumba API is Live"}

