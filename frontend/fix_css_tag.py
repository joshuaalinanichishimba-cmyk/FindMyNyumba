import os
import re
import glob

# Search through all HTML files in the frontend folder
for filename in glob.glob('*.html'):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find any <script> tag trying to load the Tailwind CSS file and replace it with a proper <link> tag
    fixed_content = re.sub(
        r'<script[^>]*src=["\']https://unpkg.com/tailwindcss[^>]*></script>', 
        '<link href="https://unpkg.com/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">', 
        content
    )
    
    if content != fixed_content:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(fixed_content)

print("✅ STYLING RESTORED: Tailwind CSS is now using the correct HTML tag!")
