"""Helpers for the postgres full-text search vector on books."""

from __future__ import annotations

from sqlalchemy import func

from app.models import Book


def book_search_text(book: Book, tag_names: list[str] | None = None) -> str:
    """Concatenate the searchable fields of a book into one string."""
    parts: list[str] = [book.title or ""]
    if book.subtitle:
        parts.append(book.subtitle)
    parts.extend(book.authors or [])
    for value in (book.publisher, book.isbn10, book.isbn13, book.description):
        if value:
            parts.append(value)
    if tag_names:
        parts.extend(tag_names)
    return " ".join(parts)


def search_vector_expr(text: str):
    """A SQL expression producing the tsvector to store on Book.search_vector."""
    return func.to_tsvector("simple", func.coalesce(text, ""))
