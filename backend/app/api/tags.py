"""Household-wide tag management (used for filtering and custom tags)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_household_access, require_member
from app.db import get_session
from app.models import BookTag, Tag, User
from app.schemas.book import TagCreate, TagOut
from app.services import serializers

router = APIRouter(prefix="/households/{household_id}/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
async def list_tags(
    household_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TagOut]:
    await require_household_access(session, user, household_id)
    tags = await session.scalars(
        select(Tag).where(Tag.household_id == household_id).order_by(Tag.name)
    )
    return [serializers.tag_out(t) for t in tags.all()]


@router.post("", response_model=TagOut, status_code=201)
async def create_tag(
    household_id: int,
    payload: TagCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TagOut:
    await require_member(session, user, household_id)
    name = payload.name.strip()
    existing = await session.scalar(
        select(Tag).where(Tag.household_id == household_id, func.lower(Tag.name) == name.lower())
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tag already exists")
    tag = Tag(household_id=household_id, name=name, color=payload.color, source="custom")
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return serializers.tag_out(tag)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    household_id: int,
    tag_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_member(session, user, household_id)
    tag = await session.get(Tag, tag_id)
    if tag is None or tag.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    await session.execute(BookTag.__table__.delete().where(BookTag.tag_id == tag_id))
    await session.delete(tag)
    await session.commit()
