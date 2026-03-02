import os, uuid
from fastapi import UploadFile, HTTPException
from PIL import Image

UPLOAD_DIR = 'uploads/listings'
MAX_SIZE = 5 * 1024 * 1024 # 5MB

async def validate_and_save_image(file: UploadFile) -> str:
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    try:
        img = Image.open(BytesIO(contents))
        img.verify()
    except:
        raise HTTPException(status_code=400, detail="Invalid image")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    
    with open(path, 'wb') as f:
        f.write(contents)
    return f"/uploads/listings/{filename}"
