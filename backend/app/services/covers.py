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


MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # 12 MB


def covers_dir() -> str:
    path = os.path.join(settings.data_dir, _COVERS_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


async def store_image(
    session: AsyncSession, household_id: int, content: bytes, content_type: str
) -> Asset | None:
    """Persist raw image bytes to the data volume as an Asset. Returns None if invalid."""
    content_type = (content_type or "").split(";")[0].strip().lower()
    # Reject empty/tiny content (e.g. Open Library's 1x1 placeholder) and non-images.
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


async def download_cover(session: AsyncSession, household_id: int, url: str) -> Asset | None:
    """Fetch a cover image from a URL and persist it as an Asset. None on failure."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content
            content_type = resp.headers.get("content-type", "image/jpeg")
    except httpx.HTTPError:
        return None
    return await store_image(session, household_id, content, content_type)
