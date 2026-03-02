from pydantic import BaseModel

class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str
    user_id: int
    username: str
    email: str
    roles: list[str]


class TokenPayload(BaseModel):
    """Schema for JWT payload"""
    user_id: int
    email: str
    username: str
    roles: list[str]
    exp: int  # Expiration timestamp