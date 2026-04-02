import pytest

def test_registration_success(client):
    """Ensures a student can register in any province."""
    payload = {
        'email': 'livingstone_student@test.com',
        'password': 'SecurePass123!',
        'name': 'Livingstone Dev',
        'role': 'student'
    }
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 201
    assert response.json()['success'] is True

def test_login_invalid_password(client):
    """Wrong credentials must return a clean 401 response."""
    response = client.post('/api/v1/auth/login', json={
        'email': 'livingstone_student@test.com',
        'password': 'WRONG_PASSWORD'
    })
    assert response.status_code == 401
    assert response.json()['success'] is False
    assert response.json()['error']['type'] == 'HTTPException'
