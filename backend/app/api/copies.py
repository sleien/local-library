"""Physical copies, including the mass-add (bulk scan) endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, require_member
from app.db import get_session
from app.models import Book, Copy, Loan, Location, User
from app.schemas.book import (
    BulkAddIn,
    BulkAddItem,
    BulkAddResult,
    CopyCreate,
    CopyOut,
    CopyUpdate,
)
from app.services import serializers
from app.services.books import create_book_from_lookup, find_book_by_isbn
from app.services.locations import build_path, get_location_map
from app.services.metadata import lookup_isbn, normalize_isbn

router = APIRouter(prefix="/households/{household_id}", tags=["copies"])


async def _validate_location(
    session: AsyncSession, household_id: int, location_id: int | None
) -> None:
    if location_id is None:
        return
    location = await session.get(Location, location_id)
    if location is None or location.household_id != household_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Location not found")


async def _active_loan(session: AsyncSession, copy_id: int) -> Loan | None:
    return await session.scalar(
        select(Loan)
        .where(Loan.copy_id == copy_id, Loan.returned_at.is_(None))
        .options(selectinload(Loan.person))
    )


@router.post("/books/{book_id}/copies", response_model=CopyOut, status_code=201)
async def create_copy(
    household_id: int,
    book_id: int,
    payload: CopyCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CopyOut:
    await require_member(session, user, household_id)
    book = await session.scalar(
        select(Book).where(Book.id == book_id, Book.household_id == household_id)
    )
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    await _validate_location(session, household_id, payload.location_id)
    copy = Copy(
        book_id=book_id,
        household_id=household_id,
        location_id=payload.location_id,
        acquired_date=payload.acquired_date,
        condition=payload.condition,
        notes=payload.notes,
    )
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    loc_map = await get_location_map(session, household_id)
    return serializers.copy_out(copy, build_path(loc_map, copy.location_id), None)


async def _get_owned_copy(session: AsyncSession, household_id: int, copy_id: int) -> Copy:
    copy = await session.get(Copy, copy_id)
    if copy is None or copy.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Copy not found")
    return copy


@router.patch("/copies/{copy_id}", response_model=CopyOut)
async def update_copy(
    household_id: int,
    copy_id: int,
    payload: CopyUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CopyOut:
    await require_member(session, user, household_id)
    copy = await _get_owned_copy(session, household_id, copy_id)
    data = payload.model_dump(exclude_unset=True)
    if "location_id" in data:
        await _validate_location(session, household_id, data["location_id"])
    for field, value in data.items():
        setattr(copy, field, value)
    await session.commit()
    await session.refresh(copy)
    loc_map = await get_location_map(session, household_id)
    active = await _active_loan(session, copy.id)
    return serializers.copy_out(copy, build_path(loc_map, copy.location_id), active)


@router.delete("/copies/{copy_id}", status_code=204)
async def delete_copy(
    household_id: int,
    copy_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_member(session, user, household_id)
    copy = await _get_owned_copy(session, household_id, copy_id)
    await session.delete(copy)
    await session.commit()


@router.post("/copies/bulk", response_model=BulkAddResult)
async def bulk_add(
    household_id: int,
    payload: BulkAddIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BulkAddResult:
    """Mass add: resolve each scanned ISBN and create a copy in the chosen location.

    Creates the book if it does not exist yet, otherwise adds another copy to the
    existing book so the same title can live in several places at once.
    """
    await require_member(session, user, household_id)
    await _validate_location(session, household_id, payload.location_id)

    items: list[BulkAddItem] = []
    added = 0
    failed = 0
    for raw in payload.isbns:
        isbn = normalize_isbn(raw)
        if not isbn:
            items.append(BulkAddItem(isbn=raw, status="error", message="Empty ISBN"))
            failed += 1
            continue
        try:
            existing = await find_book_by_isbn(session, household_id, isbn, isbn)
            if existing is None:
                lookup = await lookup_isbn(isbn)
                if lookup is None:
                    items.append(BulkAddItem(isbn=isbn, status="not_found"))
                    failed += 1
                    continue
                book = await create_book_from_lookup(session, household_id, lookup, None, [])
                outcome = "added"
            else:
                book = existing
                outcome = "copy_added"
            copy = Copy(book_id=book.id, household_id=household_id, location_id=payload.location_id)
            session.add(copy)
            await session.flush()
            items.append(
                BulkAddItem(
                    isbn=isbn,
                    status=outcome,
                    book_id=book.id,
                    copy_id=copy.id,
                    title=book.title,
                )
            )
            added += 1
        except Exception as exc:  # noqa: BLE001 - report per-item failures, keep going
            items.append(BulkAddItem(isbn=isbn, status="error", message=str(exc)))
            failed += 1
    await session.commit()
    return BulkAddResult(items=items, added=added, failed=failed)
