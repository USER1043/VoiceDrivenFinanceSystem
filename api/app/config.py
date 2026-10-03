from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Nothing else in the app reads os.environ."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://voxfin:voxfin@localhost:5432/voxfin"

    # The single owner of this instance. Seeded on startup.
    owner_email: str = "me@example.com"
    timezone: str = "Asia/Kolkata"

    # "dev" trusts every request as the owner (local only).
    # "password" requires logging in with the owner's password (required in production).
    auth_mode: Literal["dev", "password"] = "dev"
    # Argon2 hash of the owner's password; generate with `python -m app.auth hash-password`.
    owner_password_hash: str = ""
    session_days: int = 90

    # ---------- Voice and language (M2) ----------
    # All optional. Without keys, the browser does speech-to-text and a built-in rule parser
    # understands the command. Model ids live here because free tiers change them.
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_stt_model: str = "whisper-large-v3-turbo"
    groq_llm_model: str = "openai/gpt-oss-20b"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_llm_model: str = "gemini-flash-lite-latest"
    ai_timeout_seconds: float = 8.0
    pending_action_minutes: int = 10

    # Directory with the built PWA (web/dist). Served at "/" when present.
    web_dist_dir: str = "../web/dist"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, url: str) -> str:
        # Hosted Postgres (Neon, Render) hands out postgres:// URLs; SQLAlchemy needs the driver.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url

    @model_validator(mode="after")
    def _check_auth(self) -> "Settings":
        if self.environment == "production" and self.auth_mode != "password":
            raise ValueError("AUTH_MODE must be 'password' in production")
        if self.auth_mode == "password" and not self.owner_password_hash.startswith("$argon2"):
            raise ValueError("OWNER_PASSWORD_HASH must be an argon2 hash in password mode")
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
