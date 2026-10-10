import os
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

_INSECURE_SECRETS = {"", "change-me-in-production", "your_super_secret_key_change_this_in_production"}


class Settings(BaseSettings):
    # Resolve .env relative to this file so the app behaves the same
    # whether it is started from the repo root or from backend/.
    model_config = SettingsConfigDict(env_file=os.path.join(BACKEND_DIR, ".env"), extra="ignore")

    ENVIRONMENT: str = "development"  # "development" | "production"

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "relaydesk"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DATABASE_URL: str = ""

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    AUTH_COOKIE_NAME: str = "relaydesk_session"

    # Auth rate limits (per process)
    LOGIN_MAX_FAILURES_PER_ACCOUNT: int = 5   # per IP + email
    LOGIN_MAX_FAILURES_PER_IP: int = 20
    LOGIN_WINDOW_SECONDS: int = 15 * 60
    REGISTER_MAX_PER_IP: int = 10
    REGISTER_WINDOW_SECONDS: int = 60 * 60

    # Strictly free by default: the Claude API is a paid, per-request service.
    # Nothing is sent to it unless ENABLE_PAID_AI is explicitly set to true.
    ENABLE_PAID_AI: bool = False

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-5-5"
    AI_TIMEOUT_SECONDS: float = 120.0
    # Re-run classifier-declined requests on Anthropic's recommended fallback model
    AI_REFUSAL_FALLBACK: bool = True

    FRONTEND_URL: str = "http://localhost:5173"
    # Comma-separated extra origins allowed by CORS (in addition to FRONTEND_URL)
    CORS_ORIGINS: str = ""

    # Upload limits for base64 data-URL attachments
    MAX_ATTACHMENTS: int = 5
    MAX_ATTACHMENT_BYTES: int = 5 * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def cors_origins(self) -> List[str]:
        extra = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return [self.FRONTEND_URL, *extra]


settings = Settings()

if settings.is_production and settings.SECRET_KEY in _INSECURE_SECRETS:
    raise RuntimeError("SECRET_KEY must be set to a strong random value when ENVIRONMENT=production")
