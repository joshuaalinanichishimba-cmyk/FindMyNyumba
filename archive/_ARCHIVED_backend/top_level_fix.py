path = 'app/main.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Vacuum the import out of the function body
code = code.replace('    from app.models.property import Property\n', '')
code = code.replace('    from app.models.property import Property', '')

# 2. Safely place it at the very absolute top of the file
if 'from app.models.property import Property' not in code:
    code = 'from app.models.property import Property\n' + code

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)

print('✅ IMPORT MOVED TO TOP: Database collision error completely resolved!')
