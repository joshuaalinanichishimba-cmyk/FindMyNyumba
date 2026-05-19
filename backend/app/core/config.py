"""
app/core/config.py
Application settings loaded from environment variables / .env file.
SECURITY: SECRET_KEY has no default � must be set in .env or the app
will refuse to start. This prevents JWT forgery if .env is missing.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional
import secrets


class Settings(BaseSettings):
    # -- API --------------------------------------------------------------------
    API_V1_STR: str   = "/api/v1"
    PROJECT_NAME: str = "FindMyNyumba"

    # -- Database ---------------------------------------------------------------
    DATABASE_URL: str  # Required � must be set in .env

    # -- URLs -------------------------------------------------------------------
    FRONTEND_URL: str  = "http://localhost:5500"   # Update for production
    BACKEND_URL: str   = "http://127.0.0.1:8000"  # Update for production

    # -- Auth -------------------------------------------------------------------
    # SECURITY: no default value. App will crash on startup if SECRET_KEY is
    # not provided, which is intentional � a missing key means no JWT signing.
    SECRET_KEY: str
    ALGORITHM: str                    = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int  = 60 * 24 * 8  # 8 days

    # -- Admin seed (optional) --------------------------------------------------
    # Used only for the first-run admin auto-creation failsafe in admin.py.
    # Do NOT leave at default in production.
    ADMIN_SEED_EMAIL: str    = "admin@findmynyumba.com"
    ADMIN_SEED_PASSWORD: Optional[str] = None  # Must be set to enable seed

    # -- CORS -------------------------------------------------------------------
    # Comma-separated list of allowed origins.
    # Example: "http://localhost:5500,https://findmynyumba.com"
    ALLOWED_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500,https://find-my-nyumba-original.vercel.app,https://nyumba-web.vercel.app"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        return self.DATABASE_URL

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


