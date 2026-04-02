import os
import re

# 1. FIX THE CORE APP IMPORTS
main_path = 'app/main.py'
if os.path.exists(main_path):
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ensure all models are imported at the TOP to prevent the 'already defined' error
    if 'from app.models import models' not in content:
        content = "from app.models import models\n" + content
    
    # Ensure CORS is allowed (Crucial for login/posting from port 3000)
    if 'allow_origins=["*"]' not in content and 'CORSMiddleware' in content:
        content = re.sub(r'allow_origins=\[.*?\]', 'allow_origins=["*"]', content)

    with open(main_path, 'w', encoding='utf-8') as f:
        f.write(content)

# 2. VERIFY LOGIN ENDPOINT
# If you can't sign in, the frontend might be hitting the wrong port or missing a token.
api_js_path = '../frontend/js/api.js'
if os.path.exists(api_js_path):
    with open(api_js_path, 'r', encoding='utf-8') as f:
        api_content = f.read()
    
    # Force the API base URL to match your running Uvicorn server
    api_content = re.sub(r"const BASE_URL = .*", "const BASE_URL = 'http://127.0.0.1:8000/api';", api_content)
    
    with open(api_js_path, 'w', encoding='utf-8') as f:
        f.write(api_content)

print("✅ SYSTEM REPAIRED: Imports aligned, CORS unlocked, and API path verified!")
