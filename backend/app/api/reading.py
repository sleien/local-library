"""Personal reading log / timeline across all accessible libraries."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import accessible_household_ids, get_current_user
from app.db import get_session
from app.models import Book, User, UserBook
from app.schemas.book import ReadingLogEntry
from app.services import serializers

router = APIRouter(prefix="/reading-log", tags=["reading"])


@router.get("", response_model=list[ReadingLogEntry])
async def reading_log(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[ReadingLogEntry]:
    """Books the user has marked read, newest finish date first."""
    accessible = await accessible_household_ids(session, user)
    if not accessible:
        return []
    rows = await session.execute(
        select(UserBook, Book)
        .join(Book, Book.id == UserBook.book_id)
        .where(
            UserBook.user_id == user.id,
            UserBook.status == "read",
            Book.household_id.in_(accessible),
        )
        .options(selectinload(Book.selected_cover), selectinload(Book.covers))
        .order_by(
            nulls_last(UserBook.finished_at.desc()),
            nulls_last(UserBook.started_at.desc()),
            UserBook.id.desc(),
        )
    )
    return [
        ReadingLogEntry(
            book_id=book.id,
            title=book.title,
            authors=book.authors or [],
            cover_url=serializers.cover_url_for(book),
            rating=ub.rating,
            started_at=ub.started_at,
            finished_at=ub.finished_at,
            household_id=book.household_id,
        )
        for ub, book in rows.all()
    ]
