"""Household, membership, and invite schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class HouseholdOut(ORMModel):
    id: int
    name: str


class MemberOut(BaseModel):
    user_id: int
    display_name: str
    email: str
    role: str


class InviteCreate(BaseModel):
    email: EmailStr | None = None
    role: str = Field(default="member", pattern="^(owner|member)$")
    expires_in_days: int = Field(default=14, ge=1, le=365)


class InviteOut(ORMModel):
    id: int
    token: str
    email: str | None
    role: str
    expires_at: datetime | None
    accepted_at: datetime | None


class InviteAccept(BaseModel):
    token: str


class InvitePreview(BaseModel):
    household_name: str
    role: str
    valid: bool
