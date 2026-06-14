"""Borrower (person), loan, and feedback schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class PersonOut(ORMModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    notes: str | None
    user_id: int | None = None
    active_loan_count: int = 0


class FeedbackIn(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None


class FeedbackOut(ORMModel):
    rating: int | None
    comment: str | None
    created_at: datetime


class LoanCreate(BaseModel):
    copy_id: int
    # Lend to an existing borrower, or to a registered user (a linked borrower is
    # created automatically). Exactly one of these must be provided.
    person_id: int | None = None
    user_id: int | None = None
    lent_at: datetime | None = None
    due_date: datetime | None = None
    notes: str | None = None


class LoanReturn(BaseModel):
    returned_at: datetime | None = None


class LoanOut(ORMModel):
    id: int
    copy_id: int
    person_id: int
    person_name: str
    book_id: int
    book_title: str
    lent_at: datetime
    due_date: datetime | None
    returned_at: datetime | None
    is_active: bool
    is_overdue: bool
    notes: str | None
    feedback: FeedbackOut | None = None
