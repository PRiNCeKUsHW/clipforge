from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    """API settings, read from environment variables (docker compose loads them from .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    database_url: str = "postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = _DEV_SECRET
    jwt_lifetime_seconds: int = 60 * 60 * 24 * 7
    token_encryption_key: str = ""

    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_public_endpoint_url: str | None = None
    s3_access_key: str = "clipforge"
    s3_secret_key: str = "clipforge-dev-secret"
    s3_bucket: str = "clipforge"
    s3_region: str = "us-east-1"

    max_upload_mb: int = 4096
    presign_expiry_seconds: int = 3600

    # Where users land after OAuth, and the public base URL of this API (OAuth redirect URIs)
    frontend_url: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000"

    # Publishing (OAuth apps). Leave empty to hide the Connect buttons.
    google_client_id: str = ""
    google_client_secret: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_graph_version: str = "v21.0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.app_env == "production" and self.jwt_secret in ("", _DEV_SECRET, "change-me-to-a-long-random-string"):
            raise ValueError("JWT_SECRET must be set to a long random value in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
