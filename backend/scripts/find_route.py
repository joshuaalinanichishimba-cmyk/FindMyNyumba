from app.main import app
for route in app.routes:
    if hasattr(route, 'methods') and 'POST' in route.methods:
        print(route.path)
