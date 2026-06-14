"""Auth and current-user schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=200)
    # Optional: join an existing household instead of creating a new one.
    invite_token: str | None = None
    # Name for the new household when not joining via invite.
    household_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMModel):
    id: int
    email: str
    display_name: str
    is_superuser: bool


class UserSelect(ORMModel):
    """Minimal user info for pickers (inviting/sharing)."""

    id: int
    display_name: str
    email: str


class HouseholdSummary(ORMModel):
    id: int
    name: str
    role: str


class MeOut(BaseModel):
    user: UserOut
    households: list[HouseholdSummary]


class AuthConfigOut(BaseModel):
    """Public auth capabilities, used by the login screen."""

    allow_registration: bool
    oidc_enabled: bool
    oidc_display_name: str
