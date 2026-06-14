"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_name: str = "Bibliothek"
    secret_key: str = "change-me-in-production"
    # Async SQLAlchemy URL. Example: postgresql+asyncpg://user:pass@db:5432/bibliothek
    database_url: str = "postgresql+asyncpg://bibliothek:bibliothek@localhost:5432/bibliothek"
    # Directory for stored assets (cover images, later isometric uploads).
    data_dir: str = "./data"
    # Disable SQLAlchemy connection pooling (used by the test suite, which runs
    # each test on its own event loop and must not reuse asyncpg connections).
    db_disable_pool: bool = False
    # Public base URL of the deployment, used to build OIDC redirect URLs.
    public_url: str = "http://localhost:8000"

    # Optional Google Books API key. Lifts the low anonymous quota (HTTP 429),
    # improving metadata and cover coverage. Lookups work without it too.
    google_books_api_key: str | None = None

    # Auth / cookies
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = False  # set true behind HTTPS
    cookie_domain: str | None = None
    # When true, anyone can self-register a local account. When false, only invites work.
    allow_registration: bool = True

    # Authentik / OIDC (optional). When oidc_enabled is false, only local auth is used.
    oidc_enabled: bool = False
    oidc_issuer: str | None = None  # e.g. https://authentik.example.com/application/o/bibliothek/
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_scopes: str = "openid email profile"
    # If set, the human-facing name for the SSO button.
    oidc_display_name: str = "Authentik"

    @property
    def oidc_redirect_url(self) -> str:
        return f"{self.public_url.rstrip('/')}/api/auth/oidc/callback"

    @property
    def oidc_metadata_url(self) -> str | None:
        """OIDC discovery URL. Accepts either the issuer or the full
        .well-known/openid-configuration URL in OIDC_ISSUER."""
        if not self.oidc_issuer:
            return None
        base = self.oidc_issuer.rstrip("/")
        suffix = "/.well-known/openid-configuration"
        if base.endswith(suffix.lstrip("/")):
            return base
        return f"{base}{suffix}"

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
