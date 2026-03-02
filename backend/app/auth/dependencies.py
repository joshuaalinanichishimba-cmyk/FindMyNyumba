from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthenticationCredentials
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import JWTManager
from app.models.user import User
from app.schemas.token import TokenPayload
from jose import JWTError

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthenticationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token.
    
    Usage in endpoints:
        @app.get("/profile")
        def get_profile(current_user: User = Depends(get_current_user)):
            return current_user
    """
    token = credentials.credentials
    
    try:
        # Verify and decode token
        payload = JWTManager.verify_token(token)
        user_id = payload.get("user_id")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


async def get_user_roles(
    current_user: User = Depends(get_current_user)
) -> list[str]:
    """
    Get list of role names for current user.
    """
    return [role.role_name for role in current_user.roles]


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control.
    
    Usage in endpoints:
        @app.delete("/users/{user_id}")
        def delete_user(
            user_id: int,
            current_user: User = Depends(require_role("admin"))
        ):
            # Only admins can access this
    """
    async def check_role(
        current_user: User = Depends(get_current_user)
    ) -> User:
        user_roles = [role.role_name for role in current_user.roles]
        
        if not any(role in user_roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You need one of these roles: {', '.join(allowed_roles)}"
            )
        
        return current_user
    
    return check_role