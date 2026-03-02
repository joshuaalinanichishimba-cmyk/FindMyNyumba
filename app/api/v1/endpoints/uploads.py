from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
import shutil
import os
import uuid
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter()

UPLOAD_DIR = "static/uploads"

@router.post("/image")
async def upload_listing_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Create a unique filename so images don't overwrite each other
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # Save the file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Return the URL that the frontend will use to display the image
    return {"image_url": f"/static/uploads/{unique_filename}"}
