import re

file_path = r'app/main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. The perfect Image-Ready route
new_route = '''@app.post("/api/properties")
async def create_property(
    title: str = Form(...),
    description: str = Form("No description provided"),
    price: float = Form(...),
    location: str = Form("Unknown Location"),
    landlord_id: int = Form(1),
    file: UploadFile = File(None),
    db = Depends(get_db)
):
    import shutil
    import os
    import uuid
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

# 2. Slice out the old POST route and anything connected to it, stopping at the next route
pattern = re.compile(r'@app\.post\([\'"]/api/properties[\'"]\).*?(?=\n@app\.|\Z)', re.DOTALL)
new_content = re.sub(pattern, new_route, content, count=1)

# 3. Force imports at the very top if they are missing
if "UploadFile" not in new_content:
    new_content = "from fastapi import File, UploadFile, Form\n" + new_content

# 4. Save cleanly
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ SUCCESS: The shell has surgically rewritten your backend route!")
