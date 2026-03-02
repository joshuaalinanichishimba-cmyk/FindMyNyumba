from datetime import timedelta
from app.core.security import JWTManager

def create_access_token(
    user_id: int,
    email: str,
    username: str,
    roles: list[str],
    expires_delta: timedelta = None
) -> str:
    """
    Create JWT access token for authenticated user.
    
    Args:
        user_id: User ID
        email: User email
        username: User username
        roles: List of user roles
        expires_delta: Custom expiration time
        
    Returns:
        JWT token string
    """
    data = {
        "user_id": user_id,
        "email": email,
        "username": username,
        "roles": roles
    }
    
    return JWTManager.create_access_token(data, expires_delta)