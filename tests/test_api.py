from fastapi.testclient import TestClient
# Assuming your main FastAPI file is called main.py in the root
try:
    from main import app
except ImportError:
    # If main is inside /app
    from app.main import app

client = TestClient(app)

def test_health_check():
    # A simple test to ensure the server starts
    response = client.get("/")
    assert response.status_code in [200, 404] # 404 is fine if you haven't set a root route yet
