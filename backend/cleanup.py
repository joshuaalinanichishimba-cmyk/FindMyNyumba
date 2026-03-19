path = 'app/main.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Erase the conflicting import we added
code = code.replace('from app.models.property import Property\n', '')
code = code.replace('from app.models.property import Property', '')

# 2. Update our custom route to use the app's original 'models' package
code = code.replace('db_property = Property(', 'db_property = models.Property(')

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)

print('✅ CONFLICT RESOLVED: Duplicate table definition removed!')
