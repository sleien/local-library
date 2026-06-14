"""Search and filter across every book the user can access."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import accessible_household_ids, get_current_user
from app.db import get_session
from app.models import Book, BookTag, Copy, Loan, Location, User, UserBook
from app.schemas.book import BookSummary
from app.services import serializers

router = APIRouter(prefix="/search", tags=["search"])


async def _descendant_location_ids(
    session: AsyncSession, household_ids: list[int], root_id: int
) -> list[int]:
    rows = await session.execute(
        select(Location.id, Location.parent_id).where(Location.household_id.in_(household_ids))
    )
    children: dict[int, list[int]] = defaultdict(list)
    for loc_id, parent_id in rows.all():
        if parent_id is not None:
            children[parent_id].append(loc_id)
    collected = [root_id]
    queue = [root_id]
    while queue:
        current = queue.pop()
        for child in children.get(current, []):
            collected.append(child)
            queue.append(child)
    return collected


@router.get("", response_model=list[BookSummary])
async def search(
    q: str | None = None,
    household_id: int | None = None,
    tag: list[int] = Query(default=[]),
    location_id: int | None = None,
    status: str | None = Query(default=None, pattern="^(want|reading|read)$"),
    borrowed: bool | None = None,
    limit: int = 60,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[BookSummary]:
    accessible = await accessible_household_ids(session, user)
    if household_id is not None:
        accessible = [household_id] if household_id in accessible else []
    if not accessible:
        return []

    query = select(Book).where(Book.household_id.in_(accessible))

    if q:
        query = query.where(
            Book.search_vector.op("@@")(func.websearch_to_tsquery("simple", q))
        )

    if tag:
        query = query.where(
            Book.id.in_(select(BookTag.book_id).where(BookTag.tag_id.in_(tag)))
        )

    if location_id is not None:
        loc_ids = await _descendant_location_ids(session, accessible, location_id)
        query = query.where(
            Book.id.in_(select(Copy.book_id).where(Copy.location_id.in_(loc_ids)))
        )

    if status is not None:
        query = query.where(
            Book.id.in_(
                select(UserBook.book_id).where(
                    UserBook.user_id == user.id, UserBook.status == status
                )
            )
        )

    if borrowed is not None:
        on_loan = select(Copy.book_id).join(Loan, Loan.copy_id == Copy.id).where(
            Loan.returned_at.is_(None)
        )
        if borrowed:
            query = query.where(Book.id.in_(on_loan))
        else:
            query = query.where(Book.id.not_in(on_loan))

    query = (
        query.order_by(Book.title)
        .limit(min(limit, 200))
        .offset(offset)
        .options(
            selectinload(Book.tags),
            selectinload(Book.copies),
            selectinload(Book.covers),
            selectinload(Book.selected_cover),
        )
    )
    books = (await session.scalars(query)).all()

    status_rows = await session.execute(
        select(UserBook.book_id, UserBook.status).where(
            UserBook.user_id == user.id, UserBook.book_id.in_([b.id for b in books])
        )
    ) if books else None
    status_map = {bid: st for bid, st in status_rows.all()} if status_rows else {}

    return [serializers.book_summary(b, status_map.get(b.id)) for b in books]
