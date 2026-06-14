"""Pure functions that turn loaded ORM objects into response schemas.

Routers are responsible for eager-loading the relationships these functions
read (tags, copies, covers, selected_cover) and for supplying the per-user
reading status, active-loan, and comment data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models import Book, Comment, Copy, CoverCandidate, Loan, Tag, UserBook
from app.schemas.book import (
    BookDetail,
    BookSummary,
    CommentOut,
    CopyOut,
    CoverOut,
    TagOut,
    UserBookOut,
)
from app.schemas.loan import FeedbackOut, LoanOut


def tag_out(tag: Tag) -> TagOut:
    return TagOut(id=tag.id, name=tag.name, color=tag.color, source=tag.source)


def _cover_display_url(cover: CoverCandidate) -> str | None:
    if cover.asset_id:
        return f"/api/assets/{cover.asset_id}"
    return cover.source_url


def cover_url_for(book: Book) -> str | None:
    """Best displayable cover URL: the selected one, else any downloaded, else any remote."""
    if book.selected_cover is not None:
        url = _cover_display_url(book.selected_cover)
        if url:
            return url
    for cover in book.covers:
        if cover.asset_id:
            return f"/api/assets/{cover.asset_id}"
    for cover in book.covers:
        if cover.source_url:
            return cover.source_url
    return None


def cover_out_list(book: Book) -> list[CoverOut]:
    return [
        CoverOut(
            id=c.id,
            source=c.source,
            source_url=c.source_url,
            asset_id=c.asset_id,
            url=_cover_display_url(c),
            width=c.width,
            height=c.height,
            selected=(c.id == book.selected_cover_id),
        )
        for c in book.covers
    ]


def copy_out(copy: Copy, loc_path: str | None, active_loan: Loan | None) -> CopyOut:
    return CopyOut(
        id=copy.id,
        book_id=copy.book_id,
        location_id=copy.location_id,
        location_path=loc_path,
        acquired_date=copy.acquired_date,
        condition=copy.condition,
        notes=copy.notes,
        is_borrowed=active_loan is not None,
        borrowed_by=active_loan.person.name if active_loan and active_loan.person else None,
    )


def book_summary(book: Book, my_status: str | None) -> BookSummary:
    return BookSummary(
        id=book.id,
        title=book.title,
        subtitle=book.subtitle,
        authors=book.authors or [],
        isbn13=book.isbn13,
        cover_url=cover_url_for(book),
        tags=[tag_out(t) for t in book.tags],
        copy_count=len(book.copies),
        my_status=my_status,
    )


def comment_out(comment: Comment, user_name: str) -> CommentOut:
    return CommentOut(
        id=comment.id,
        body=comment.body,
        user_id=comment.user_id,
        user_name=user_name,
        created_at=comment.created_at,
    )


def user_book_out(ub: UserBook | None) -> UserBookOut | None:
    if ub is None:
        return None
    return UserBookOut(
        status=ub.status,
        rating=ub.rating,
        review=ub.review,
        started_at=ub.started_at,
        finished_at=ub.finished_at,
    )


def loan_out(loan: Loan, book_title: str, person_name: str) -> LoanOut:
    now = datetime.now(UTC)
    due = loan.due_date
    if due is not None and due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    is_active = loan.returned_at is None
    is_overdue = is_active and due is not None and due < now
    feedback = None
    if loan.feedback is not None:
        feedback = FeedbackOut(
            rating=loan.feedback.rating,
            comment=loan.feedback.comment,
            created_at=loan.feedback.created_at,
        )
    return LoanOut(
        id=loan.id,
        copy_id=loan.copy_id,
        person_id=loan.person_id,
        person_name=person_name,
        book_id=loan.copy.book_id if loan.copy else 0,
        book_title=book_title,
        lent_at=loan.lent_at,
        due_date=loan.due_date,
        returned_at=loan.returned_at,
        is_active=is_active,
        is_overdue=is_overdue,
        notes=loan.notes,
        feedback=feedback,
    )


def book_detail(
    book: Book,
    my_book: UserBook | None,
    copies: list[CopyOut],
    comments: list[CommentOut],
) -> BookDetail:
    return BookDetail(
        id=book.id,
        title=book.title,
        subtitle=book.subtitle,
        authors=book.authors or [],
        isbn13=book.isbn13,
        isbn10=book.isbn10,
        publisher=book.publisher,
        published_date=book.published_date,
        page_count=book.page_count,
        language=book.language,
        description=book.description,
        metadata_source=book.metadata_source,
        cover_url=cover_url_for(book),
        tags=[tag_out(t) for t in book.tags],
        copy_count=len(book.copies),
        my_status=my_book.status if my_book else None,
        covers=cover_out_list(book),
        copies=copies,
        comments=comments,
        my_book=user_book_out(my_book),
    )
