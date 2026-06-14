"""Personal API token schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TokenOut(ORMModel):
    id: int
    name: str
    prefix: str
    last_used_at: datetime | None
    created_at: datetime


class TokenCreated(TokenOut):
    # The full token, shown only once at creation time.
    token: str
