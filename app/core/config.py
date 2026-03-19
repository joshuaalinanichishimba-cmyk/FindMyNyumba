from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    DEBUG: bool = True
    PROJECT_NAME: str = "FindMyNyumba"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-super-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # We provide EVERY possible name the app might ask for
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///./findmynyumba.db"
    DATABASE_URL: str = "sqlite:///./findmynyumba.db"

    class Config:
        case_sensitive = True

settings = Settings()
print("--- [SYSTEM CHECK]: Settings Loaded with DATABASE_URL! ---")
