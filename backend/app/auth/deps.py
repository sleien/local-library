"""Authentication and authorization dependencies."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import ACCESS_TOKEN_COOKIE, decode_token, hash_api_token
from app.db import get_session
from app.models import ApiToken, HouseholdMembership, HouseholdShare, User


async def _user_from_bearer(request: Request, session: AsyncSession) -> User | None:
    """Authenticate via an Authorization: Bearer <api-token> header, if present."""
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    raw = header.split(" ", 1)[1].strip()
    token = await session.scalar(
        select(ApiToken).where(ApiToken.token_hash == hash_api_token(raw))
    )
    if token is None:
        return None
    user = await session.get(User, token.user_id)
    if user is None or not user.is_active:
        return None
    token.last_used_at = datetime.now(UTC)
    await session.commit()
    return user


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    # Cookie session (browser) takes precedence; fall back to a personal API token.
    cookie = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if cookie:
        user_id = decode_token(cookie, "access")
        if user_id is not None:
            user = await session.get(User, user_id)
            if user is not None and user.is_active:
                return user

    user = await _user_from_bearer(request, session)
    if user is not None:
        return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


async def accessible_household_ids(session: AsyncSession, user: User) -> list[int]:
    """Household ids the user may read: their memberships plus shared-to-them ones."""
    member_ids = await session.scalars(
        select(HouseholdMembership.household_id).where(HouseholdMembership.user_id == user.id)
    )
    shared_ids = await session.scalars(
        select(HouseholdShare.household_id).where(HouseholdShare.viewer_user_id == user.id)
    )
    return list(dict.fromkeys([*member_ids.all(), *shared_ids.all()]))


async def get_membership(
    session: AsyncSession, user: User, household_id: int
) -> HouseholdMembership | None:
    return await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.user_id == user.id,
            HouseholdMembership.household_id == household_id,
        )
    )


async def require_member(
    session: AsyncSession, user: User, household_id: int, *, require_owner: bool = False
) -> HouseholdMembership:
    """Ensure the user belongs to the household; optionally require the owner role."""
    membership = await get_membership(session, user, household_id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    if require_owner and membership.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner role required")
    return membership


async def require_household_access(
    session: AsyncSession, user: User, household_id: int
) -> None:
    """Ensure the user can read the household (member in v1; shared friends in phase 2)."""
    if household_id not in await accessible_household_ids(session, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
