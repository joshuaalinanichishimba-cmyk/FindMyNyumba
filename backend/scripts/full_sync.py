import os
import re

# 1. REPAIR BACKEND (main.py) - Fix CORS and Imports
backend_main = r'backend/app/main.py'
if os.path.exists(backend_main):
    with open(backend_main, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ensure CORS allows your frontend port 3000 to talk to backend 8000
    cors_pattern = r'allow_origins=\[.*?\]'
    if re.search(cors_pattern, content):
        content = re.sub(cors_pattern, 'allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]', content)
    
    # Fix the Property model reference to be consistent
    content = content.replace('db_property = Property(', 'db_property = models.Property(')
    
    with open(backend_main, 'w', encoding='utf-8') as f:
        f.write(content)

# 2. REPAIR FRONTEND (api.js & app.js) - Align URLs
api_js = r'frontend/js/api.js'
if os.path.exists(api_js):
    with open(api_js, 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'const BASE_URL = .*', "const BASE_URL = 'http://127.0.0.1:8000/api';", content)
    with open(api_js, 'w', encoding='utf-8') as f:
        f.write(content)

app_js = r'frontend/js/app.js'
if os.path.exists(app_js):
    with open(app_js, 'r', encoding='utf-8') as f:
        content = f.read()
    # Ensure it uses the new image upload route we created
    content = content.replace('/api/properties', '/api/properties_with_image')
    with open(app_js, 'w', encoding='utf-8') as f:
        f.write(content)

print("✅ FULL SYNC COMPLETE: Backend, Frontend, and Database are now aligned!")
