"""Book, copy, cover, tag, reading-status, and comment schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

# --- Tags -------------------------------------------------------------------


class TagOut(ORMModel):
    id: int
    name: str
    color: str | None
    source: str


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=20)


# --- Covers -----------------------------------------------------------------


class CoverOut(BaseModel):
    id: int
    source: str
    source_url: str | None
    asset_id: int | None
    url: str | None  # best displayable URL (downloaded asset or remote source)
    width: int | None = None
    height: int | None = None
    selected: bool = False


class LookupCover(BaseModel):
    source: str
    url: str
    width: int | None = None
    height: int | None = None


class LookupResult(BaseModel):
    """Normalised metadata returned by an ISBN lookup, before a book is created."""

    title: str
    subtitle: str | None = None
    authors: list[str] = []
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = None
    language: str | None = None
    description: str | None = None
    subjects: list[str] = []
    covers: list[LookupCover] = []
    sources: list[str] = []


# --- Reading status & comments ----------------------------------------------


class UserBookIn(BaseModel):
    status: str = Field(default="want", pattern="^(want|reading|read)$")
    rating: int | None = Field(default=None, ge=1, le=5)
    review: str | None = None
    started_at: date | None = None
    finished_at: date | None = None


class UserBookOut(ORMModel):
    status: str
    rating: int | None
    review: str | None
    started_at: date | None
    finished_at: date | None


class CommentIn(BaseModel):
    body: str = Field(min_length=1)


class CommentOut(BaseModel):
    id: int
    body: str
    user_id: int
    user_name: str
    created_at: datetime


# --- Copies -----------------------------------------------------------------


class CopyCreate(BaseModel):
    location_id: int | None = None
    acquired_date: date | None = None
    condition: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class CopyUpdate(BaseModel):
    location_id: int | None = None
    acquired_date: date | None = None
    condition: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class CopyOut(ORMModel):
    id: int
    book_id: int
    location_id: int | None
    location_path: str | None = None
    acquired_date: date | None
    condition: str | None
    notes: str | None
    # Borrowing summary, filled in by the router.
    is_borrowed: bool = False
    borrowed_by: str | None = None


# --- Books ------------------------------------------------------------------


class BookManualCreate(BaseModel):
    """Create a book by hand (no lookup)."""

    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = None
    authors: list[str] = []
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = None
    language: str | None = None
    description: str | None = None
    tags: list[str] = []


class BookFromLookup(BaseModel):
    """Create a book from a previously fetched lookup result."""

    isbn: str
    # When omitted, the server re-runs the lookup for the ISBN.
    lookup: LookupResult | None = None
    # Index into lookup.covers to mark selected; null means first available.
    selected_cover_index: int | None = None
    extra_tags: list[str] = []


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    subtitle: str | None = None
    authors: list[str] | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = None
    language: str | None = None
    description: str | None = None


class BookSummary(ORMModel):
    id: int
    title: str
    subtitle: str | None
    authors: list[str]
    isbn13: str | None
    cover_url: str | None = None
    tags: list[TagOut] = []
    copy_count: int = 0
    my_status: str | None = None


class BookDetail(BookSummary):
    isbn10: str | None
    publisher: str | None
    published_date: str | None
    page_count: int | None
    language: str | None
    description: str | None
    metadata_source: str | None
    covers: list[CoverOut] = []
    copies: list[CopyOut] = []
    comments: list[CommentOut] = []
    my_book: UserBookOut | None = None


# --- Mass add ---------------------------------------------------------------


class ShelfCopyLocation(BaseModel):
    copy_id: int
    location_path: str | None = None
    is_borrowed: bool = False
    borrowed_by: str | None = None


class ShelfLocateOut(BaseModel):
    """Where a scanned book should be put back."""

    isbn: str
    found: bool
    book_id: int | None = None
    title: str | None = None
    authors: list[str] = []
    cover_url: str | None = None
    copies: list[ShelfCopyLocation] = []


class ReadingLogEntry(BaseModel):
    """One read book with the dates it was read, for the timeline."""

    book_id: int
    title: str
    authors: list[str] = []
    cover_url: str | None = None
    rating: int | None = None
    started_at: date | None = None
    finished_at: date | None = None
    household_id: int | None = None


class BulkAddIn(BaseModel):
    location_id: int | None = None
    isbns: list[str] = Field(min_length=1)


class BulkAddItem(BaseModel):
    isbn: str
    status: str  # added | duplicate_copy | not_found | error
    book_id: int | None = None
    copy_id: int | None = None
    title: str | None = None
    message: str | None = None


class BulkAddResult(BaseModel):
    items: list[BulkAddItem]
    added: int
    failed: int
