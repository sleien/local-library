"""Serve stored assets (cover images) to authorised household members."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_household_access
from app.config import settings
from app.db import get_session
from app.models import Asset, User

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/{asset_id}")
async def get_asset(
    asset_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    await require_household_access(session, user, asset.household_id)
    abs_path = os.path.join(settings.data_dir, asset.path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing on disk")
    return FileResponse(abs_path, media_type=asset.content_type)
