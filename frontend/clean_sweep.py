import re

html_path = 'dashboard-landlord.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Tailwind to a more stable 'Development' version to reduce console noise
content = content.replace('https://cdn.tailwindcss.com', 'https://unpkg.com/tailwindcss@^2/dist/tailwind.min.css')

# 2. Force-inject 'name' and 'id' into any input that is missing them
def repair_inputs(match):
    tag = match.group(0)
    if 'name=' in tag:
        return tag
    # Use the placeholder text to create a name (e.g., 'Property Title' -> 'property_title')
    placeholder = re.search(r'placeholder=["\']([^"\']+)["\']', tag)
    if placeholder:
        clean_name = placeholder.group(1).lower().replace(' ', '_')
        return tag.replace('>', f' name="{clean_name}" id="{clean_name}">')
    return tag

content = re.sub(r'<input[^>]+>', repair_inputs, content)
content = re.sub(r'<textarea[^>]+>', repair_inputs, content)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ HTML CLEANED: Tailwind updated and Form Fields labeled!')
