"""Authentication endpoints: local accounts plus optional Authentik OIDC."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.auth.deps import get_current_user
from app.auth.security import REFRESH_TOKEN_COOKIE, decode_token, hash_password, verify_password
from app.config import settings
from app.db import get_session
from app.models import Household, HouseholdInvite, HouseholdMembership, User
from app.schemas.auth import (
    AuthConfigOut,
    HouseholdSummary,
    LoginIn,
    MeOut,
    RegisterIn,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def build_me(session: AsyncSession, user: User) -> MeOut:
    rows = await session.execute(
        select(Household.id, Household.name, HouseholdMembership.role)
        .join(HouseholdMembership, HouseholdMembership.household_id == Household.id)
        .where(HouseholdMembership.user_id == user.id)
        .order_by(Household.id)
    )
    households = [
        HouseholdSummary(id=hid, name=name, role=role) for hid, name, role in rows.all()
    ]
    return MeOut(user=UserOut.model_validate(user), households=households)


@router.get("/config", response_model=AuthConfigOut)
async def auth_config() -> AuthConfigOut:
    return AuthConfigOut(
        allow_registration=settings.allow_registration,
        oidc_enabled=settings.oidc_enabled,
        oidc_display_name=settings.oidc_display_name,
    )


async def _consume_invite(session: AsyncSession, token: str) -> HouseholdInvite:
    invite = await session.scalar(select(HouseholdInvite).where(HouseholdInvite.token == token))
    if invite is None or invite.accepted_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or already used invite")
    if invite.expires_at and invite.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invite has expired")
    return invite


@router.post("/register", response_model=MeOut)
async def register(
    payload: RegisterIn, response: Response, session: AsyncSession = Depends(get_session)
) -> MeOut:
    existing = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    invite = await _consume_invite(session, payload.invite_token) if payload.invite_token else None
    if invite is None and not settings.allow_registration:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Self-registration is disabled; an invite is required"
        )

    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    await session.flush()

    if invite is not None:
        session.add(
            HouseholdMembership(
                user_id=user.id, household_id=invite.household_id, role=invite.role
            )
        )
        invite.accepted_at = datetime.now(UTC)
    else:
        household = Household(name=payload.household_name or f"{payload.display_name}'s Library")
        session.add(household)
        await session.flush()
        session.add(
            HouseholdMembership(user_id=user.id, household_id=household.id, role="owner")
        )

    await session.commit()
    await session.refresh(user)
    set_auth_cookies(response, user.id)
    return await build_me(session, user)


@router.post("/login", response_model=MeOut)
async def login(
    payload: LoginIn, response: Response, session: AsyncSession = Depends(get_session)
) -> MeOut:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.hashed_password or not verify_password(
        payload.password, user.hashed_password
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    set_auth_cookies(response, user.id)
    return await build_me(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/refresh", response_model=MeOut)
async def refresh(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> MeOut:
    token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    user_id = decode_token(token, "refresh") if token else None
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    set_auth_cookies(response, user.id)
    return await build_me(session, user)


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> MeOut:
    return await build_me(session, user)


# --- OIDC (Authentik) -------------------------------------------------------


@router.get("/oidc/login")
async def oidc_login(request: Request):
    if not settings.oidc_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC is not enabled")
    from app.auth.oidc import get_oauth

    oauth = get_oauth()
    return await oauth.authentik.authorize_redirect(request, settings.oidc_redirect_url)


@router.get("/oidc/callback")
async def oidc_callback(request: Request, session: AsyncSession = Depends(get_session)):
    if not settings.oidc_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC is not enabled")
    from app.auth.oidc import get_oauth

    oauth = get_oauth()
    try:
        token = await oauth.authentik.authorize_access_token(request)
    except Exception as exc:  # noqa: BLE001 - surface provider errors as 400
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"OIDC exchange failed: {exc}") from exc

    userinfo = token.get("userinfo") or {}
    subject = userinfo.get("sub")
    email = (userinfo.get("email") or "").lower() or None
    name = userinfo.get("name") or userinfo.get("preferred_username") or email or "User"
    if not subject:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OIDC response missing subject")

    user = await session.scalar(select(User).where(User.oidc_subject == subject))
    if user is None and email:
        user = await session.scalar(select(User).where(User.email == email))
        if user is not None:
            user.oidc_subject = subject  # link existing local account
    if user is None:
        user = User(
            email=email or f"{subject}@oidc.local",
            display_name=name,
            oidc_subject=subject,
        )
        session.add(user)
        await session.flush()
        household = Household(name=f"{name}'s Library")
        session.add(household)
        await session.flush()
        session.add(
            HouseholdMembership(user_id=user.id, household_id=household.id, role="owner")
        )
    await session.commit()
    await session.refresh(user)

    redirect = RedirectResponse(url=settings.public_url or "/")
    set_auth_cookies(redirect, user.id)
    return redirect
