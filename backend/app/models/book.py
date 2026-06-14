"""Bibliographic records, physical copies, cover candidates, tags, and notes."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


class Asset(Base, TimestampMixin):
    """A stored file on the data volume (cover images, later isometric uploads)."""

    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")


class Book(Base, TimestampMixin):
    """Bibliographic record. The same title can back many physical copies."""

    __tablename__ = "book"
    __table_args__ = (
        Index("ix_book_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authors: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    isbn10: Mapped[str | None] = mapped_column(String(13), index=True, nullable=True)
    isbn13: Mapped[str | None] = mapped_column(String(17), index=True, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(300), nullable=True)
    published_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    selected_cover_id: Mapped[int | None] = mapped_column(
        ForeignKey("cover_candidate.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    # Maintained in the service layer (postgres full-text search).
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    copies: Mapped[list[Copy]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    covers: Mapped[list[CoverCandidate]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        foreign_keys="CoverCandidate.book_id",
    )
    selected_cover: Mapped[CoverCandidate | None] = relationship(
        foreign_keys=[selected_cover_id], post_update=True
    )
    tags: Mapped[list[Tag]] = relationship(secondary="book_tag", back_populates="books")
    comments: Mapped[list[Comment]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )


class CoverCandidate(Base, TimestampMixin):
    """A candidate cover image pulled from a metadata provider; the user picks one."""

    __tablename__ = "cover_candidate"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset.id", ondelete="SET NULL"), nullable=True
    )
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    book: Mapped[Book] = relationship(back_populates="covers", foreign_keys=[book_id])
    asset: Mapped[Asset | None] = relationship()


class Copy(Base, TimestampMixin):
    """A physical instance of a book in the household."""

    __tablename__ = "copy"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True, index=True
    )
    acquired_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    condition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    book: Mapped[Book] = relationship(back_populates="copies")
    location: Mapped[Location | None] = relationship()  # noqa: F821
    loans: Mapped[list[Loan]] = relationship(  # noqa: F821
        back_populates="copy", cascade="all, delete-orphan"
    )


class Tag(Base, TimestampMixin):
    __tablename__ = "tag"
    __table_args__ = (UniqueConstraint("household_id", "name", name="uq_tag_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # "auto" tags come from online metadata subjects; "custom" tags are user-defined.
    source: Mapped[str] = mapped_column(String(20), default="custom", nullable=False)

    books: Mapped[list[Book]] = relationship(secondary="book_tag", back_populates="tags")


class BookTag(Base):
    __tablename__ = "book_tag"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("book.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)


class UserBook(Base, TimestampMixin):
    """A user's personal relationship to a book: read status, rating, review."""

    __tablename__ = "user_book"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    # want | reading | read
    status: Mapped[str] = mapped_column(String(20), default="want", nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    finished_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class Comment(Base, TimestampMixin):
    """A household comment on a book."""

    __tablename__ = "comment"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text, nullable=False)

    book: Mapped[Book] = relationship(back_populates="comments")
    user: Mapped[User] = relationship()  # noqa: F821
