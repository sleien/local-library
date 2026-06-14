"""Books: creation (lookup or manual), detail, covers, tags, status, comments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, require_household_access, require_member
from app.db import get_session
from app.models import Book, Comment, Loan, Tag, User, UserBook
from app.schemas.book import (
    BookDetail,
    BookFromLookup,
    BookManualCreate,
    BookSummary,
    BookUpdate,
    CommentIn,
    CommentOut,
    TagCreate,
    TagOut,
    UserBookIn,
    UserBookOut,
)
from app.services import serializers
from app.services.books import (
    apply_search_vector,
    create_book_from_lookup,
    find_book_by_isbn,
    get_or_create_tags,
    set_book_tags,
)
from app.services.covers import download_cover
from app.services.locations import build_path, get_location_map
from app.services.metadata import lookup_isbn, normalize_isbn

router = APIRouter(prefix="/households/{household_id}/books", tags=["books"])

_DETAIL_LOADS = (
    selectinload(Book.tags),
    selectinload(Book.copies),
    selectinload(Book.covers),
    selectinload(Book.selected_cover),
    selectinload(Book.comments).selectinload(Comment.user),
)


async def _load_book(session: AsyncSession, household_id: int, book_id: int) -> Book:
    book = await session.scalar(
        select(Book)
        .where(Book.id == book_id, Book.household_id == household_id)
        .options(*_DETAIL_LOADS)
    )
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    return book


async def _active_loans_for_copies(session: AsyncSession, copy_ids: list[int]) -> dict[int, Loan]:
    if not copy_ids:
        return {}
    loans = await session.scalars(
        select(Loan)
        .where(Loan.copy_id.in_(copy_ids), Loan.returned_at.is_(None))
        .options(selectinload(Loan.person))
    )
    return {loan.copy_id: loan for loan in loans.all()}


async def _build_detail(session: AsyncSession, book: Book, user_id: int) -> BookDetail:
    loc_map = await get_location_map(session, book.household_id)
    active = await _active_loans_for_copies(session, [c.id for c in book.copies])
    copies = [
        serializers.copy_out(c, build_path(loc_map, c.location_id), active.get(c.id))
        for c in sorted(book.copies, key=lambda c: c.id)
    ]
    comments = [
        serializers.comment_out(c, c.user.display_name if c.user else "Unknown")
        for c in sorted(book.comments, key=lambda c: c.created_at)
    ]
    my_book = await session.scalar(
        select(UserBook).where(UserBook.user_id == user_id, UserBook.book_id == book.id)
    )
    return serializers.book_detail(book, my_book, copies, comments)


@router.get("", response_model=list[BookSummary])
async def list_books(
    household_id: int,
    limit: int = 60,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[BookSummary]:
    await require_household_access(session, user, household_id)
    books = (
        await session.scalars(
            select(Book)
            .where(Book.household_id == household_id)
            .order_by(Book.created_at.desc(), Book.id.desc())
            .limit(min(limit, 200))
            .offset(offset)
            .options(
                selectinload(Book.tags),
                selectinload(Book.copies),
                selectinload(Book.covers),
                selectinload(Book.selected_cover),
            )
        )
    ).all()
    status_map = await _status_map(session, user.id, [b.id for b in books])
    return [serializers.book_summary(b, status_map.get(b.id)) for b in books]


async def _status_map(
    session: AsyncSession, user_id: int, book_ids: list[int]
) -> dict[int, str]:
    if not book_ids:
        return {}
    rows = await session.execute(
        select(UserBook.book_id, UserBook.status).where(
            UserBook.user_id == user_id, UserBook.book_id.in_(book_ids)
        )
    )
    return {bid: st for bid, st in rows.all()}


@router.post("/from-lookup", response_model=BookDetail)
async def create_from_lookup(
    household_id: int,
    payload: BookFromLookup,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BookDetail:
    await require_member(session, user, household_id)
    lookup = payload.lookup or await lookup_isbn(payload.isbn)
    if lookup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No metadata found for that ISBN")

    existing = await find_book_by_isbn(session, household_id, lookup.isbn10, lookup.isbn13)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        book = await _load_book(session, household_id, existing.id)
        return await _build_detail(session, book, user.id)

    book = await create_book_from_lookup(
        session, household_id, lookup, payload.selected_cover_index, payload.extra_tags
    )
    await session.commit()
    response.status_code = status.HTTP_201_CREATED
    book = await _load_book(session, household_id, book.id)
    return await _build_detail(session, book, user.id)


@router.post("/manual", response_model=BookDetail, status_code=201)
async def create_manual(
    household_id: int,
    payload: BookManualCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BookDetail:
    await require_member(session, user, household_id)
    book = Book(
        household_id=household_id,
        title=payload.title,
        subtitle=payload.subtitle,
        authors=payload.authors,
        isbn10=normalize_isbn(payload.isbn10) if payload.isbn10 else None,
        isbn13=normalize_isbn(payload.isbn13) if payload.isbn13 else None,
        publisher=payload.publisher,
        published_date=payload.published_date,
        page_count=payload.page_count,
        language=payload.language,
        description=payload.description,
        metadata_source="manual",
    )
    session.add(book)
    await session.flush()
    tags = await get_or_create_tags(session, household_id, payload.tags, source="custom")
    await set_book_tags(session, book, tags)
    await apply_search_vector(session, book, [t.name for t in tags])
    await session.commit()
    book = await _load_book(session, household_id, book.id)
    return await _build_detail(session, book, user.id)


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(
    household_id: int,
    book_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BookDetail:
    await require_household_access(session, user, household_id)
    book = await _load_book(session, household_id, book_id)
    return await _build_detail(session, book, user.id)


@router.patch("/{book_id}", response_model=BookDetail)
async def update_book(
    household_id: int,
    book_id: int,
    payload: BookUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BookDetail:
    await require_member(session, user, household_id)
    book = await _load_book(session, household_id, book_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    await apply_search_vector(session, book)
    await session.commit()
    book = await _load_book(session, household_id, book_id)
    return await _build_detail(session, book, user.id)


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    household_id: int,
    book_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_member(session, user, household_id)
    book = await session.scalar(
        select(Book).where(Book.id == book_id, Book.household_id == household_id)
    )
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    await session.delete(book)
    await session.commit()


@router.post("/{book_id}/select-cover/{cover_id}", response_model=BookDetail)
async def select_cover(
    household_id: int,
    book_id: int,
    cover_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BookDetail:
    await require_member(session, user, household_id)
    book = await _load_book(session, household_id, book_id)
    cover = next((c for c in book.covers if c.id == cover_id), None)
    if cover is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cover not found")
    if cover.asset_id is None and cover.source_url:
        asset = await download_cover(session, household_id, cover.source_url)
        if asset is not None:
            cover.asset_id = asset.id
    book.selected_cover_id = cover.id
    await session.commit()
    book = await _load_book(session, household_id, book_id)
    return await _build_detail(session, book, user.id)


@router.post("/{book_id}/tags", response_model=list[TagOut])
async def add_tag(
    household_id: int,
    book_id: int,
    payload: TagCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TagOut]:
    await require_member(session, user, household_id)
    book = await _load_book(session, household_id, book_id)
    tags = await get_or_create_tags(session, household_id, [payload.name], source="custom")
    if tags and payload.color:
        tags[0].color = payload.color
    for tag in tags:
        if tag.id not in {t.id for t in book.tags}:
            book.tags.append(tag)
    await apply_search_vector(session, book)
    await session.commit()
    book = await _load_book(session, household_id, book_id)
    return [serializers.tag_out(t) for t in book.tags]


@router.delete("/{book_id}/tags/{tag_id}", response_model=list[TagOut])
async def remove_tag(
    household_id: int,
    book_id: int,
    tag_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TagOut]:
    await require_member(session, user, household_id)
    book = await _load_book(session, household_id, book_id)
    book.tags = [t for t in book.tags if t.id != tag_id]
    await apply_search_vector(session, book)
    await session.commit()
    book = await _load_book(session, household_id, book_id)
    return [serializers.tag_out(t) for t in book.tags]


@router.put("/{book_id}/status", response_model=UserBookOut)
async def set_status(
    household_id: int,
    book_id: int,
    payload: UserBookIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserBookOut:
    await require_household_access(session, user, household_id)
    book = await session.scalar(
        select(Book).where(Book.id == book_id, Book.household_id == household_id)
    )
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    ub = await session.scalar(
        select(UserBook).where(UserBook.user_id == user.id, UserBook.book_id == book_id)
    )
    if ub is None:
        ub = UserBook(user_id=user.id, book_id=book_id)
        session.add(ub)
    ub.status = payload.status
    ub.rating = payload.rating
    ub.review = payload.review
    ub.started_at = payload.started_at
    ub.finished_at = payload.finished_at
    await session.commit()
    await session.refresh(ub)
    return serializers.user_book_out(ub)


@router.post("/{book_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment(
    household_id: int,
    book_id: int,
    payload: CommentIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CommentOut:
    await require_household_access(session, user, household_id)
    book = await session.scalar(
        select(Book).where(Book.id == book_id, Book.household_id == household_id)
    )
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    comment = Comment(book_id=book_id, user_id=user.id, body=payload.body)
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return serializers.comment_out(comment, user.display_name)


@router.delete("/{book_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    household_id: int,
    book_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_household_access(session, user, household_id)
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.book_id != book_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    membership = await require_member(session, user, household_id)
    if comment.user_id != user.id and membership.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete another member's comment")
    await session.delete(comment)
    await session.commit()


@router.get("/{book_id}/tags-available", response_model=list[TagOut])
async def household_tags(
    household_id: int,
    book_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TagOut]:
    """All tags defined in the household (for autocomplete when tagging a book)."""
    await require_household_access(session, user, household_id)
    tags = await session.scalars(
        select(Tag).where(Tag.household_id == household_id).order_by(Tag.name)
    )
    return [serializers.tag_out(t) for t in tags.all()]
