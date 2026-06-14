"""Borrowers (people) and their lending history (person view)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, require_household_access, require_member
from app.db import get_session
from app.models import Copy, Loan, Person, User
from app.schemas.loan import LoanOut, PersonCreate, PersonOut, PersonUpdate
from app.services import serializers

router = APIRouter(prefix="/households/{household_id}/people", tags=["people"])


async def _active_counts(session: AsyncSession, household_id: int) -> dict[int, int]:
    rows = await session.execute(
        select(Loan.person_id, func.count(Loan.id))
        .where(Loan.household_id == household_id, Loan.returned_at.is_(None))
        .group_by(Loan.person_id)
    )
    return {pid: count for pid, count in rows.all()}


def _person_out(person: Person, active: int) -> PersonOut:
    return PersonOut(
        id=person.id,
        name=person.name,
        email=person.email,
        phone=person.phone,
        notes=person.notes,
        user_id=person.user_id,
        active_loan_count=active,
    )


@router.get("", response_model=list[PersonOut])
async def list_people(
    household_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PersonOut]:
    await require_household_access(session, user, household_id)
    people = await session.scalars(
        select(Person).where(Person.household_id == household_id).order_by(Person.name)
    )
    counts = await _active_counts(session, household_id)
    return [_person_out(p, counts.get(p.id, 0)) for p in people.all()]


@router.post("", response_model=PersonOut, status_code=201)
async def create_person(
    household_id: int,
    payload: PersonCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PersonOut:
    await require_member(session, user, household_id)
    person = Person(
        household_id=household_id,
        name=payload.name,
        email=payload.email.lower() if payload.email else None,
        phone=payload.phone,
        notes=payload.notes,
    )
    session.add(person)
    await session.commit()
    await session.refresh(person)
    return _person_out(person, 0)


async def _get_owned_person(session: AsyncSession, household_id: int, person_id: int) -> Person:
    person = await session.get(Person, person_id)
    if person is None or person.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    return person


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    household_id: int,
    person_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PersonOut:
    await require_household_access(session, user, household_id)
    person = await _get_owned_person(session, household_id, person_id)
    counts = await _active_counts(session, household_id)
    return _person_out(person, counts.get(person.id, 0))


@router.patch("/{person_id}", response_model=PersonOut)
async def update_person(
    household_id: int,
    person_id: int,
    payload: PersonUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PersonOut:
    await require_member(session, user, household_id)
    person = await _get_owned_person(session, household_id, person_id)
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        data["email"] = data["email"].lower()
    for field, value in data.items():
        setattr(person, field, value)
    await session.commit()
    await session.refresh(person)
    counts = await _active_counts(session, household_id)
    return _person_out(person, counts.get(person.id, 0))


@router.delete("/{person_id}", status_code=204)
async def delete_person(
    household_id: int,
    person_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_member(session, user, household_id)
    person = await _get_owned_person(session, household_id, person_id)
    await session.delete(person)
    await session.commit()


@router.get("/{person_id}/loans", response_model=list[LoanOut])
async def person_loans(
    household_id: int,
    person_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LoanOut]:
    """Which books this person has had, and when (person view)."""
    await require_household_access(session, user, household_id)
    await _get_owned_person(session, household_id, person_id)
    loans = await session.scalars(
        select(Loan)
        .where(Loan.household_id == household_id, Loan.person_id == person_id)
        .order_by(Loan.lent_at.desc())
        .options(
            selectinload(Loan.copy).selectinload(Copy.book),
            selectinload(Loan.person),
            selectinload(Loan.feedback),
        )
    )
    return [
        serializers.loan_out(
            loan,
            loan.copy.book.title if loan.copy and loan.copy.book else "Unknown",
            loan.person.name if loan.person else "Unknown",
        )
        for loan in loans.all()
    ]
