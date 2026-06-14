"""Authentication and authorization dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import ACCESS_TOKEN_COOKIE, decode_token
from app.db import get_session
from app.models import HouseholdMembership, User


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = decode_token(token, "access")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


async def accessible_household_ids(session: AsyncSession, user: User) -> list[int]:
    """Household ids the user may read. In v1 this equals their memberships."""
    result = await session.scalars(
        select(HouseholdMembership.household_id).where(HouseholdMembership.user_id == user.id)
    )
    return list(result.all())


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
