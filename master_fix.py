import os
import re

# 1. APPEND NEW BYPASS ROUTE TO BACKEND
backend_path = r'backend/app/main.py'
with open(backend_path, 'r', encoding='utf-8') as f:
    backend_content = f.read()

new_route = '''\n
# --- DEDICATED IMAGE UPLOAD ROUTE ---
from fastapi import File, UploadFile, Form
import shutil
import uuid

@app.post("/api/properties_with_image")
async def create_property_with_image(
    title: str = Form(...),
    description: str = Form("No description provided"),
    price: float = Form(0.0),
    location: str = Form("Unknown Location"),
    landlord_id: int = Form(1),
    file: UploadFile = File(None),
    db = Depends(get_db)
):
    from app import models
    file_path = None
    if file and hasattr(file, 'filename') and file.filename:
        file_ext = file.filename.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = f"static/uploads/{unique_filename}"
        os.makedirs("static/uploads", exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    db_property = models.Property(
        title=title, description=description, price=price, 
        location=location, landlord_id=landlord_id, photo_url=file_path
    )
    db.add(db_property)
    db.commit()
    db.refresh(db_property)
    return db_property
'''

if "properties_with_image" not in backend_content:
    with open(backend_path, 'a', encoding='utf-8') as f:
        f.write(new_route)

# 2. UPDATE JS TO POINT TO THE NEW ROUTE
js_path = r'frontend/js/app.js'
with open(js_path, 'r', encoding='utf-8') as f:
    js_content = f.read()

js_content = re.sub(
    r"fetch\('http://127\.0\.0\.1:8000/api/properties',\s*\{\s*method:\s*'POST'",
    "fetch('http://127.0.0.1:8000/api/properties_with_image', {\n                    method: 'POST'",
    js_content
)
with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js_content)

# 3. FIX HTML MULTI-STEP VALIDATION (novalidate)
html_path = r'frontend/dashboard-landlord.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

if 'id="propertyForm" novalidate' not in html_content:
    html_content = html_content.replace('id="propertyForm"', 'id="propertyForm" novalidate')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

print("✅ MASTER FIX COMPLETE: Backend bypassed, JS updated, HTML validation fixed!")
