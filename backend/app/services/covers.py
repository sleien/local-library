"""Download and store cover images on the data volume."""

from __future__ import annotations

import hashlib
import mimetypes
import os

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Asset

_COVERS_SUBDIR = "covers"
_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def covers_dir() -> str:
    path = os.path.join(settings.data_dir, _COVERS_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


async def download_cover(session: AsyncSession, household_id: int, url: str) -> Asset | None:
    """Fetch a cover image and persist it as an Asset. Returns None on failure."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content
            content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    except httpx.HTTPError:
        return None
    # Open Library returns a tiny 1x1 placeholder when no cover exists.
    if not content or len(content) < 256:
        return None
    if not content_type.startswith("image/"):
        return None

    ext = _EXT_BY_TYPE.get(content_type) or mimetypes.guess_extension(content_type) or ".jpg"
    digest = hashlib.sha256(content).hexdigest()[:32]
    filename = f"{digest}{ext}"
    abs_path = os.path.join(covers_dir(), filename)
    if not os.path.exists(abs_path):
        with open(abs_path, "wb") as fh:
            fh.write(content)

    asset = Asset(
        household_id=household_id,
        path=os.path.join(_COVERS_SUBDIR, filename),
        content_type=content_type,
    )
    session.add(asset)
    await session.flush()
    return asset
