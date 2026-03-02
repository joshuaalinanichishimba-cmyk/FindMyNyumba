from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "FindMyNyumba"
    SECRET_KEY: str = "SUPER_SECRET_KEY_123_DO_NOT_USE_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = "sqlite:///./test.db"
    DEBUG: bool = False  # Add this to handle the 'debug' input

    class Config:
        env_file = ".env"
        extra = "ignore"  # This tells Pydantic: "If you see extra stuff, just ignore it"

settings = Settings()
