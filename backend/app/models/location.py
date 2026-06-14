"""Self-referential location tree (e.g. Room > Shelf > Section)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


class Location(Base, TimestampMixin):
    __tablename__ = "location"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Free-form classifier; the tree is not hardcoded. Suggested: room|unit|section|custom.
    kind: Mapped[str] = mapped_column(String(40), default="custom", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Reserved for the future isometric shelf map (coordinates / polygon regions).
    position: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    parent: Mapped[Location | None] = relationship(
        back_populates="children", remote_side="Location.id"
    )
    children: Mapped[list[Location]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
