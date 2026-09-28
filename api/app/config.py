from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Nothing else in the app reads os.environ."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://voxfin:voxfin@localhost:5432/voxfin"

    # The single owner of this instance. Seeded on startup and the only email allowed in.
    owner_email: str = "me@example.com"
    timezone: str = "Asia/Kolkata"

    # "dev" trusts every request as the owner (local only).
    # "cloudflare" requires a valid Cloudflare Access JWT for the owner's email.
    auth_mode: Literal["dev", "cloudflare"] = "dev"
    cf_access_team_domain: str = ""  # e.g. "myteam.cloudflareaccess.com"
    cf_access_aud: str = ""  # Application Audience (AUD) tag

    # Directory with the built PWA (web/dist). Served at "/" when present.
    web_dist_dir: str = "../web/dist"

    @model_validator(mode="after")
    def _check_auth(self) -> "Settings":
        if self.environment == "production" and self.auth_mode != "cloudflare":
            raise ValueError("AUTH_MODE must be 'cloudflare' in production")
        if self.auth_mode == "cloudflare" and not (
            self.cf_access_team_domain and self.cf_access_aud
        ):
            raise ValueError("CF_ACCESS_TEAM_DOMAIN and CF_ACCESS_AUD are required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
