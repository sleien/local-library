"""Helpers to set and clear auth cookies on responses."""

from __future__ import annotations

from fastapi import Response

from app.auth.security import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    create_access_token,
    create_refresh_token,
)
from app.config import settings


def set_auth_cookies(response: Response, user_id: int) -> None:
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access,
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
        **common,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        path="/",
        **common,
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE):
        response.delete_cookie(name, path="/", domain=settings.cookie_domain)
