# backend/app/api/v1/auth.py
from fastapi import Depends

def get_current_user():
    """
    Temporary stub for current_user.
    Replace with real authentication logic later.
    """
    return {"id": 1, "role": "admin"}  # for testing, assume admin user