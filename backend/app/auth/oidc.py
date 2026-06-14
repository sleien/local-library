"""Optional Authentik / OpenID Connect client built on Authlib."""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth

from app.config import settings

_oauth: OAuth | None = None


def get_oauth() -> OAuth:
    """Return a configured Authlib OAuth registry with the 'authentik' client.

    Uses OIDC discovery against the configured issuer so the authorize/token/
    userinfo endpoints and signing keys are resolved automatically.
    """
    global _oauth
    if _oauth is None:
        oauth = OAuth()
        oauth.register(
            name="authentik",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            server_metadata_url=settings.oidc_metadata_url,
            client_kwargs={"scope": settings.oidc_scopes},
        )
        _oauth = oauth
    return _oauth
