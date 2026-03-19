import os
import re
import glob

# 1. Restore HTML files to original state (Remove injected scripts/links)
for filename in glob.glob('*.html'):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove any injected FormValidator scripts
    content = re.sub(r'<script>\s*class FormValidator.*?</script>', '', content, flags=re.DOTALL)
    # Revert Tailwind CSS to the original CDN version
    content = content.replace('https://unpkg.com/tailwindcss@2.2.19/dist/tailwind.min.css', 'https://cdn.tailwindcss.com')
    content = content.replace('<link href="https://cdn.tailwindcss.com" rel="stylesheet">', '<script src="https://cdn.tailwindcss.com"></script>')
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

# 2. Reset api.js to standard base URL
api_path = 'js/api.js'
if os.path.exists(api_path):
    with open(api_path, 'w', encoding='utf-8') as f:
        f.write("const BASE_URL = 'http://127.0.0.1:8000/api';\n")

print("♻️  RESTORE COMPLETE: Frontend files have been reset to their original state.")
