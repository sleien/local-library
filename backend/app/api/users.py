"""Directory of registered users, used by the invite/share pickers."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_session
from app.models import User
from app.schemas.auth import UserSelect

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserSelect])
async def list_users(
    _: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[User]:
    """All active users, so an owner can pick who to invite or share with."""
    result = await session.scalars(
        select(User).where(User.is_active.is_(True)).order_by(User.display_name)
    )
    return list(result.all())
