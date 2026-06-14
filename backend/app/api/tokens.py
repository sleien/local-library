"""Personal API tokens for programmatic access (Authorization: Bearer)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.security import generate_api_token, hash_api_token
from app.db import get_session
from app.models import ApiToken, User
from app.schemas.token import TokenCreate, TokenCreated, TokenOut

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("", response_model=list[TokenOut])
async def list_tokens(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[ApiToken]:
    result = await session.scalars(
        select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.id.desc())
    )
    return list(result.all())


@router.post("", response_model=TokenCreated, status_code=201)
async def create_token(
    payload: TokenCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TokenCreated:
    plaintext, prefix = generate_api_token()
    token = ApiToken(
        user_id=user.id,
        name=payload.name,
        token_hash=hash_api_token(plaintext),
        prefix=prefix,
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return TokenCreated(
        id=token.id,
        name=token.name,
        prefix=token.prefix,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        token=plaintext,
    )


@router.delete("/{token_id}", status_code=204)
async def revoke_token(
    token_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    token = await session.get(ApiToken, token_id)
    if token is None or token.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
    await session.delete(token)
    await session.commit()
