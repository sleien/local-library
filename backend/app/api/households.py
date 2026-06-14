"""Household management: creation, members, and invitations."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_member
from app.db import get_session
from app.models import (
    Household,
    HouseholdInvite,
    HouseholdMembership,
    HouseholdShare,
    User,
)
from app.schemas.household import (
    HouseholdCreate,
    HouseholdOut,
    InviteAccept,
    InviteCreate,
    InviteOut,
    InvitePreview,
    MemberOut,
    ShareCreate,
    ShareOut,
)

router = APIRouter(tags=["households"])


@router.get("/households", response_model=list[HouseholdOut])
async def list_households(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[Household]:
    result = await session.scalars(
        select(Household)
        .join(HouseholdMembership, HouseholdMembership.household_id == Household.id)
        .where(HouseholdMembership.user_id == user.id)
        .order_by(Household.id)
    )
    return list(result.all())


@router.post("/households", response_model=HouseholdOut, status_code=status.HTTP_201_CREATED)
async def create_household(
    payload: HouseholdCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Household:
    household = Household(name=payload.name)
    session.add(household)
    await session.flush()
    session.add(HouseholdMembership(user_id=user.id, household_id=household.id, role="owner"))
    await session.commit()
    await session.refresh(household)
    return household


@router.get("/households/{household_id}/members", response_model=list[MemberOut])
async def list_members(
    household_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MemberOut]:
    await require_member(session, user, household_id)
    rows = await session.execute(
        select(User.id, User.display_name, User.email, HouseholdMembership.role)
        .join(HouseholdMembership, HouseholdMembership.user_id == User.id)
        .where(HouseholdMembership.household_id == household_id)
        .order_by(HouseholdMembership.role.desc(), User.display_name)
    )
    return [
        MemberOut(user_id=uid, display_name=name, email=email, role=role)
        for uid, name, email, role in rows.all()
    ]


@router.delete("/households/{household_id}/members/{member_id}", status_code=204)
async def remove_member(
    household_id: int,
    member_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_member(session, user, household_id, require_owner=True)
    if member_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove yourself")
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == member_id,
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    await session.delete(membership)
    await session.commit()


@router.post("/households/{household_id}/invites", response_model=InviteOut, status_code=201)
async def create_invite(
    household_id: int,
    payload: InviteCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> HouseholdInvite:
    await require_member(session, user, household_id, require_owner=True)
    invite = HouseholdInvite(
        household_id=household_id,
        token=secrets.token_urlsafe(24),
        email=payload.email.lower() if payload.email else None,
        role=payload.role,
        invited_by_user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    return invite


@router.get("/households/{household_id}/invites", response_model=list[InviteOut])
async def list_invites(
    household_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[HouseholdInvite]:
    await require_member(session, user, household_id, require_owner=True)
    result = await session.scalars(
        select(HouseholdInvite)
        .where(HouseholdInvite.household_id == household_id, HouseholdInvite.accepted_at.is_(None))
        .order_by(HouseholdInvite.id.desc())
    )
    return list(result.all())


@router.delete("/households/{household_id}/invites/{invite_id}", status_code=204)
async def revoke_invite(
    household_id: int,
    invite_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_member(session, user, household_id, require_owner=True)
    invite = await session.get(HouseholdInvite, invite_id)
    if invite is None or invite.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    await session.delete(invite)
    await session.commit()


@router.get("/households/{household_id}/shares", response_model=list[ShareOut])
async def list_shares(
    household_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ShareOut]:
    await require_member(session, user, household_id)
    rows = await session.execute(
        select(HouseholdShare.id, User.id, User.display_name, User.email)
        .join(User, User.id == HouseholdShare.viewer_user_id)
        .where(HouseholdShare.household_id == household_id)
        .order_by(User.display_name)
    )
    return [
        ShareOut(id=sid, viewer_user_id=uid, viewer_name=name, viewer_email=email)
        for sid, uid, name, email in rows.all()
    ]


@router.post("/households/{household_id}/shares", response_model=ShareOut, status_code=201)
async def create_share(
    household_id: int,
    payload: ShareCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ShareOut:
    """Grant a registered user read-only access to this household's collection."""
    await require_member(session, user, household_id, require_owner=True)
    target = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No user with that email; they must register first"
        )
    member = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == target.id,
        )
    )
    if member is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That user is already a member")
    existing = await session.scalar(
        select(HouseholdShare).where(
            HouseholdShare.household_id == household_id,
            HouseholdShare.viewer_user_id == target.id,
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already shared with that user")
    share = HouseholdShare(household_id=household_id, viewer_user_id=target.id)
    session.add(share)
    await session.commit()
    await session.refresh(share)
    return ShareOut(
        id=share.id,
        viewer_user_id=target.id,
        viewer_name=target.display_name,
        viewer_email=target.email,
    )


@router.delete("/households/{household_id}/shares/{share_id}", status_code=204)
async def revoke_share(
    household_id: int,
    share_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_member(session, user, household_id, require_owner=True)
    share = await session.get(HouseholdShare, share_id)
    if share is None or share.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    await session.delete(share)
    await session.commit()


@router.get("/invites/{token}", response_model=InvitePreview)
async def preview_invite(
    token: str, session: AsyncSession = Depends(get_session)
) -> InvitePreview:
    invite = await session.scalar(select(HouseholdInvite).where(HouseholdInvite.token == token))
    valid = bool(
        invite
        and invite.accepted_at is None
        and (invite.expires_at is None or invite.expires_at >= datetime.now(UTC))
    )
    name = ""
    if invite:
        household = await session.get(Household, invite.household_id)
        name = household.name if household else ""
    return InvitePreview(
        household_name=name, role=invite.role if invite else "member", valid=valid
    )


@router.post("/invites/accept", response_model=HouseholdOut)
async def accept_invite(
    payload: InviteAccept,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Household:
    invite = await session.scalar(
        select(HouseholdInvite).where(HouseholdInvite.token == payload.token)
    )
    if invite is None or invite.accepted_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or already used invite")
    if invite.expires_at and invite.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invite has expired")
    existing = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == invite.household_id,
            HouseholdMembership.user_id == user.id,
        )
    )
    if existing is None:
        session.add(
            HouseholdMembership(
                user_id=user.id, household_id=invite.household_id, role=invite.role
            )
        )
    invite.accepted_at = datetime.now(UTC)
    await session.commit()
    household = await session.get(Household, invite.household_id)
    return household
