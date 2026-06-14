"""Borrowers (people) and the lending history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


class Person(Base, TimestampMixin):
    """Someone a copy can be lent to. Not necessarily an app user."""

    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional link to a registered app user, so members/friends can be lent to directly.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )

    loans: Mapped[list[Loan]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class Loan(Base, TimestampMixin):
    """A copy lent to a person. An open loan has returned_at = NULL."""

    __tablename__ = "loan"

    id: Mapped[int] = mapped_column(primary_key=True)
    copy_id: Mapped[int] = mapped_column(ForeignKey("copy.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), index=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    lender_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    lent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    copy: Mapped[Copy] = relationship(back_populates="loans")  # noqa: F821
    person: Mapped[Person] = relationship(back_populates="loans")
    feedback: Mapped[LoanFeedback | None] = relationship(
        back_populates="loan", cascade="all, delete-orphan", uselist=False
    )


class LoanFeedback(Base, TimestampMixin):
    """The borrower's rating and comment about the book for a given loan."""

    __tablename__ = "loan_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(
        ForeignKey("loan.id", ondelete="CASCADE"), unique=True, index=True
    )
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    loan: Mapped[Loan] = relationship(back_populates="feedback")
