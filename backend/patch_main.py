import re
import os

file_path = r'app/main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add missing imports safely
if 'UploadFile' not in content:
    content = content.replace('from fastapi import FastAPI', 'from fastapi import FastAPI, Form, File, UploadFile')
if 'import shutil' not in content:
    content = 'import shutil\nimport os\n' + content

# 2. The new Image-Ready Route (with safety defaults to prevent 422 errors)
new_route = '''@app.post("/api/properties")
async def create_property(
    title: str = Form(...),
    description: str = Form("No description provided"),
    price: float = Form(...),
    location: str = Form("Location not specified"),
    landlord_id: int = Form(1),
    file: UploadFile = File(None),
    db = Depends(get_db)
):
    from app import models
    file_path = None
    if file and file.filename:
        import uuid
        file_ext = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = f"static/uploads/{unique_filename}"
        
        os.makedirs("static/uploads", exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    db_property = models.Property(
        title=title, 
        description=description, 
        price=price, 
        location=location, 
        landlord_id=landlord_id, 
        photo_url=file_path
    )
    db.add(db_property)
    db.commit()
    db.refresh(db_property)
    return db_property

'''

# 3. Replace the old route using a powerful regex
pattern = re.compile(r'@app\.post\([\'"]/api/properties[\'"]\).*?(?=@app\.|\Z)', re.DOTALL)
new_content = re.sub(pattern, new_route, content, count=1)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ Backend route successfully patched for Image Uploads!')
