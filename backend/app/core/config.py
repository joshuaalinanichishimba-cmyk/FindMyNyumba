"""
app/core/config.py
Application settings loaded from environment variables / .env file.
SECURITY: SECRET_KEY has no default â€” must be set in .env or the app
will refuse to start. This prevents JWT forgery if .env is missing.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    # -- API --------------------------------------------------------------------
    API_V1_STR: str   = "/api/v1"
    PROJECT_NAME: str = "FindMyNyumba"

    # -- Database ---------------------------------------------------------------
    DATABASE_URL: str  # Required â€” must be set in .env

    # -- Environment ------------------------------------------------------------
    # Set PRODUCTION=true in production .env.
    # Controls dev-only behaviour such as debug token logging.
    PRODUCTION: bool = False

    # -- URLs -------------------------------------------------------------------
    FRONTEND_URL: str = "https://find-my-nyumba-original.vercel.app"
    BACKEND_URL: str  = "http://127.0.0.1:8000"  # Update for production

    # -- Auth -------------------------------------------------------------------
    SECRET_KEY: str
    GOOGLE_CLIENT_ID: str            = "194165956778-4k6oied4jds8ofbbnfr98h3ueeteclmb.apps.googleusercontent.com"
    GOOGLE_CLIENT_ID: str            = "194165956778-4k6oied4jds8ofbbnfr98h3ueeteclmb.apps.googleusercontent.com"
    ALGORITHM: str                   = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # -- Email (Resend) ---------------------------------------------------------
    # Sign up free at https://resend.com â†’ API Keys â†’ Create Key
    # Add a verified sender domain in Resend dashboard, then set MAIL_FROM.
    RESEND_API_KEY: str              = ""          # Required in production
    MAIL_FROM: str                   = "onboarding@resend.dev"
    MAIL_FROM_NAME: str              = "FindMyNyumba"

    # -- Cloudinary (image hosting) --------------------------------------------
    # Sign up free at https://cloudinary.com â†’ Dashboard â†’ API Keys
    CLOUDINARY_CLOUD_NAME: str       = ""
    CLOUDINARY_API_KEY: str          = ""
    CLOUDINARY_API_SECRET: str       = ""

    # -- Admin seed (optional) --------------------------------------------------
    ADMIN_SEED_EMAIL: str            = "admin@findmynyumba.com"
    ADMIN_SEED_PASSWORD: Optional[str] = None

    # -- CORS -------------------------------------------------------------------
    ALLOWED_ORIGINS: str = (
        "http://localhost:5500,"
        "http://127.0.0.1:5500,"
        "https://find-my-nyumba-original.vercel.app,"
        "https://nyumba-web.vercel.app"
    )

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




