path = 'app/main.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

import_fix = '''    try:
        from app.models.property import Property
    except ImportError:
        from app.models.models import Property'''

code = code.replace('    from app import models', import_fix)
code = code.replace('models.Property(', 'Property(')

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)

print('✅ DATABASE LINK FIXED: Pointed directly to your nested property files!')
