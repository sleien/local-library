"""Business logic for creating and maintaining books."""

from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, BookTag, CoverCandidate, Tag
from app.schemas.book import LookupResult
from app.services.covers import download_cover
from app.services.search import book_search_text, search_vector_expr


async def get_or_create_tags(
    session: AsyncSession, household_id: int, names: list[str], source: str
) -> list[Tag]:
    """Resolve tag names to Tag rows for a household, creating any that are missing."""
    cleaned = list(dict.fromkeys(n.strip() for n in names if n and n.strip()))
    if not cleaned:
        return []
    existing = await session.scalars(
        select(Tag).where(Tag.household_id == household_id, Tag.name.in_(cleaned))
    )
    by_name = {t.name: t for t in existing.all()}
    tags: list[Tag] = []
    for name in cleaned:
        tag = by_name.get(name)
        if tag is None:
            tag = Tag(household_id=household_id, name=name, source=source)
            session.add(tag)
            await session.flush()
            by_name[name] = tag
        tags.append(tag)
    return tags


async def find_book_by_isbn(
    session: AsyncSession, household_id: int, isbn10: str | None, isbn13: str | None
) -> Book | None:
    conditions = []
    if isbn13:
        conditions.append(Book.isbn13 == isbn13)
    if isbn10:
        conditions.append(Book.isbn10 == isbn10)
    if not conditions:
        return None
    return await session.scalar(
        select(Book).where(Book.household_id == household_id, or_(*conditions))
    )


async def set_book_tags(session: AsyncSession, book: Book, tags: list[Tag]) -> None:
    """Replace a book's tag associations via the association table.

    Writing BookTag rows directly avoids triggering a lazy load of the
    (possibly unloaded) book.tags collection inside the async session.
    """
    await session.execute(delete(BookTag).where(BookTag.book_id == book.id))
    seen: set[int] = set()
    for tag in tags:
        if tag.id not in seen:
            session.add(BookTag(book_id=book.id, tag_id=tag.id))
            seen.add(tag.id)
    await session.flush()


async def apply_search_vector(
    session: AsyncSession, book: Book, tag_names: list[str] | None = None
) -> None:
    """Recompute and store the full-text search vector for a book.

    Pass tag_names explicitly when book.tags is not eager-loaded.
    """
    if tag_names is None:
        tag_names = [t.name for t in book.tags]
    text = book_search_text(book, tag_names)
    book.search_vector = search_vector_expr(text)


async def create_book_from_lookup(
    session: AsyncSession,
    household_id: int,
    lookup: LookupResult,
    selected_cover_index: int | None,
    extra_tags: list[str],
) -> Book:
    """Create a Book (plus cover candidates and tags) from a lookup result."""
    book = Book(
        household_id=household_id,
        title=lookup.title,
        subtitle=lookup.subtitle,
        authors=lookup.authors,
        isbn10=lookup.isbn10,
        isbn13=lookup.isbn13,
        publisher=lookup.publisher,
        published_date=lookup.published_date,
        page_count=lookup.page_count,
        language=lookup.language,
        description=lookup.description,
        metadata_source="+".join(lookup.sources) or None,
    )
    session.add(book)
    await session.flush()

    # Cover candidates.
    candidates: list[CoverCandidate] = []
    for cover in lookup.covers:
        cc = CoverCandidate(
            book_id=book.id,
            source=cover.source,
            source_url=cover.url,
            width=cover.width,
            height=cover.height,
        )
        session.add(cc)
        candidates.append(cc)
    await session.flush()

    # Choose and download a cover. Start at the requested index, but fall
    # through to the other candidates so a missing/placeholder image does not
    # leave the book without a usable cover.
    if candidates:
        start = selected_cover_index if selected_cover_index is not None else 0
        start = max(0, min(start, len(candidates) - 1))
        order = [start, *[i for i in range(len(candidates)) if i != start]]
        chosen = candidates[start]
        for i in order:
            candidate = candidates[i]
            if not candidate.source_url:
                continue
            asset = await download_cover(session, household_id, candidate.source_url)
            if asset is not None:
                candidate.asset_id = asset.id
                chosen = candidate
                break
        book.selected_cover_id = chosen.id

    # Tags: auto from subjects, plus any custom extras.
    auto = await get_or_create_tags(session, household_id, lookup.subjects, source="auto")
    custom = await get_or_create_tags(session, household_id, extra_tags, source="custom")
    combined = list({t.id: t for t in [*auto, *custom]}.values())
    await set_book_tags(session, book, combined)

    await apply_search_vector(session, book, [t.name for t in combined])
    await session.flush()
    return book
