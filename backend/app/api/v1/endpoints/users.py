"""
app/api/v1/endpoints/users.py
"""
import os
import traceback

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()

# Cloudinary — same account/config used for listing media (env vars set on Render)
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True,
)

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_IMAGE_MB = 8


@router.post("/register", response_model=UserResponse)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(User).filter(User.email == user_in.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # SECURITY: never trust role from the client. Public signup can only
        # create student / student_host / landlord — never admin/staff.
        _allowed_roles = {"student", "student_host", "landlord"}
        _safe_role = user_in.role if user_in.role in _allowed_roles else "student"

        new_user = User(
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            full_name=user_in.full_name,
            role=_safe_role,
            is_active=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except HTTPException:
        # Don't let the generic handler below turn a 400 into a 500.
        raise
    except Exception as e:
        db.rollback()
        print("--- ERROR DETECTED ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/me/photo")
async def upload_my_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Profile photo upload for ANY logged-in user (student, student_host, landlord).
    Saves the Cloudinary URL onto the user's existing avatar_url column.
    """
    mime = (file.content_type or "").lower()
    if mime not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime}.")

    data = await file.read()
    if len(data) > _MAX_IMAGE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {_MAX_IMAGE_MB}MB limit.")

    try:
        result = cloudinary.uploader.upload(
            data,
            folder="findmynyumba/avatars",
            resource_type="image",
            transformation=[{"width": 400, "height": 400, "crop": "fill",
                             "gravity": "face", "quality": "auto"}],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Photo upload failed: {str(e)}")

    current_user.avatar_url = result["secure_url"]
    db.commit()
    return {"status": "success", "avatar_url": current_user.avatar_url}
