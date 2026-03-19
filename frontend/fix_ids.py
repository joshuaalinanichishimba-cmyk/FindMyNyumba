import re

html_path = 'dashboard-landlord.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# This finds inputs/textareas missing names and gives them one based on their placeholder or type
def add_attributes(match):
    tag = match.group(0)
    if 'name=' in tag or 'id=' in tag:
        return tag
    
    # Generate a name based on placeholder text
    placeholder_match = re.search(r'placeholder=["\']([^"\']+)["\']', tag)
    if placeholder_match:
        name = placeholder_match.group(1).lower().replace(' ', '_')
        return tag.replace('>', f' name="{name}" id="{name}">')
    return tag

# Apply to all inputs and textareas
content = re.sub(r'<input[^>]+>', add_attributes, content)
content = re.sub(r'<textarea[^>]+>', add_attributes, content)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ HTML REPAIR: Missing name and id attributes have been added!')
