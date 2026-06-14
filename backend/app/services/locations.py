"""Helpers for working with the location tree."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location

PATH_SEP = " / "


async def get_location_map(session: AsyncSession, household_id: int) -> dict[int, Location]:
    result = await session.scalars(
        select(Location).where(Location.household_id == household_id)
    )
    return {loc.id: loc for loc in result.all()}


def build_path(loc_map: dict[int, Location], loc_id: int | None, sep: str = PATH_SEP) -> str | None:
    """Return the full breadcrumb label for a location id, e.g. 'Office / Shelf 1 / Left'."""
    if loc_id is None or loc_id not in loc_map:
        return None
    parts: list[str] = []
    seen: set[int] = set()
    current: int | None = loc_id
    while current is not None and current in loc_map and current not in seen:
        seen.add(current)
        loc = loc_map[current]
        parts.append(loc.name)
        current = loc.parent_id
    return sep.join(reversed(parts))
