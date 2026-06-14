"""Lending: create loans, return them, record borrower feedback, view history."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, require_household_access, require_member
from app.db import get_session
from app.models import Copy, Loan, LoanFeedback, Person, User
from app.schemas.loan import FeedbackIn, FeedbackOut, LoanCreate, LoanOut, LoanReturn
from app.services import serializers

router = APIRouter(prefix="/households/{household_id}", tags=["loans"])

_LOAN_LOADS = (
    selectinload(Loan.copy).selectinload(Copy.book),
    selectinload(Loan.person),
    selectinload(Loan.feedback),
)


async def _load_loan(session: AsyncSession, household_id: int, loan_id: int) -> Loan:
    loan = await session.scalar(
        select(Loan)
        .where(Loan.id == loan_id, Loan.household_id == household_id)
        .options(*_LOAN_LOADS)
    )
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loan not found")
    return loan


def _serialize(loan: Loan) -> LoanOut:
    return serializers.loan_out(
        loan,
        loan.copy.book.title if loan.copy and loan.copy.book else "Unknown",
        loan.person.name if loan.person else "Unknown",
    )


@router.get("/loans", response_model=list[LoanOut])
async def list_loans(
    household_id: int,
    active: bool | None = None,
    person_id: int | None = None,
    copy_id: int | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LoanOut]:
    await require_household_access(session, user, household_id)
    query = select(Loan).where(Loan.household_id == household_id).options(*_LOAN_LOADS)
    if active is True:
        query = query.where(Loan.returned_at.is_(None))
    elif active is False:
        query = query.where(Loan.returned_at.is_not(None))
    if person_id is not None:
        query = query.where(Loan.person_id == person_id)
    if copy_id is not None:
        query = query.where(Loan.copy_id == copy_id)
    loans = await session.scalars(query.order_by(Loan.lent_at.desc()))
    return [_serialize(loan) for loan in loans.all()]


@router.post("/loans", response_model=LoanOut, status_code=201)
async def lend(
    household_id: int,
    payload: LoanCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LoanOut:
    await require_member(session, user, household_id)

    copy = await session.get(Copy, payload.copy_id)
    if copy is None or copy.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Copy not found")
    person = await session.get(Person, payload.person_id)
    if person is None or person.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")

    open_loan = await session.scalar(
        select(Loan).where(Loan.copy_id == copy.id, Loan.returned_at.is_(None))
    )
    if open_loan is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This copy is already on loan")

    loan = Loan(
        copy_id=copy.id,
        person_id=person.id,
        household_id=household_id,
        lender_user_id=user.id,
        lent_at=payload.lent_at or datetime.now(UTC),
        due_date=payload.due_date,
        notes=payload.notes,
    )
    session.add(loan)
    await session.commit()
    return _serialize(await _load_loan(session, household_id, loan.id))


@router.post("/loans/{loan_id}/return", response_model=LoanOut)
async def return_loan(
    household_id: int,
    loan_id: int,
    payload: LoanReturn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LoanOut:
    await require_member(session, user, household_id)
    loan = await _load_loan(session, household_id, loan_id)
    if loan.returned_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Loan is already returned")
    loan.returned_at = payload.returned_at or datetime.now(UTC)
    await session.commit()
    return _serialize(await _load_loan(session, household_id, loan_id))


@router.put("/loans/{loan_id}/feedback", response_model=FeedbackOut)
async def set_feedback(
    household_id: int,
    loan_id: int,
    payload: FeedbackIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FeedbackOut:
    """Record the borrower's rating and comment about the book for this loan."""
    await require_member(session, user, household_id)
    loan = await _load_loan(session, household_id, loan_id)
    feedback = loan.feedback
    if feedback is None:
        feedback = LoanFeedback(loan_id=loan.id)
        session.add(feedback)
    feedback.rating = payload.rating
    feedback.comment = payload.comment
    await session.commit()
    await session.refresh(feedback)
    return FeedbackOut(
        rating=feedback.rating, comment=feedback.comment, created_at=feedback.created_at
    )


@router.get("/copies/{copy_id}/loans", response_model=list[LoanOut])
async def copy_loan_history(
    household_id: int,
    copy_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LoanOut]:
    """Full lending history for one copy (book view)."""
    await require_household_access(session, user, household_id)
    copy = await session.get(Copy, copy_id)
    if copy is None or copy.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Copy not found")
    loans = await session.scalars(
        select(Loan)
        .where(Loan.copy_id == copy_id, Loan.household_id == household_id)
        .order_by(Loan.lent_at.desc())
        .options(*_LOAN_LOADS)
    )
    return [_serialize(loan) for loan in loans.all()]
