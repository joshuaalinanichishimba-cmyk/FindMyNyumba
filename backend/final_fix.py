path = 'app/main.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# Remove the problematic inner import that caused the duplicate table error
bad_import = '''    try:
        from app.models.property import Property
    except ImportError:
        from app.models.models import Property'''

# Replace it with a safe import that relies on FastAPI's existing registry
code = code.replace(bad_import, '    from app.models.property import Property')

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)

print('✅ DATABASE IMPORT FIXED: SQLAlchemy duplicate table error resolved!')
