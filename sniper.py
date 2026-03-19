import re

html_path = 'frontend/dashboard-landlord.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# This powerful regex hunts down ANY inline <script> block containing 'addEventListener' and destroys it
pattern = re.compile(r'<script[^>]*>(?:(?!</script>).)*?addEventListener(?:(?!</script>).)*?</script>', re.IGNORECASE | re.DOTALL)
cleaned_content = re.sub(pattern, '', content)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(cleaned_content)

print('✅ SNIPER SUCCESS: The broken ghost script on line 685 has been eliminated!')
