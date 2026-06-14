"""Location tree CRUD. The hierarchy is fully user-defined (not hardcoded)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_household_access, require_member
from app.db import get_session
from app.models import Location, User
from app.schemas.location import LocationCreate, LocationNode, LocationOut, LocationUpdate
from app.services.locations import build_path, get_location_map

router = APIRouter(prefix="/households/{household_id}/locations", tags=["locations"])


def _build_tree(locations: list[Location]) -> list[LocationNode]:
    loc_map = {loc.id: loc for loc in locations}
    nodes: dict[int, LocationNode] = {}
    for loc in locations:
        nodes[loc.id] = LocationNode(
            id=loc.id,
            household_id=loc.household_id,
            parent_id=loc.parent_id,
            name=loc.name,
            kind=loc.kind,
            sort_order=loc.sort_order,
            path=build_path(loc_map, loc.id) or loc.name,
            children=[],
        )
    roots: list[LocationNode] = []
    for loc in locations:
        node = nodes[loc.id]
        if loc.parent_id and loc.parent_id in nodes:
            nodes[loc.parent_id].children.append(node)
        else:
            roots.append(node)

    def sort_rec(items: list[LocationNode]) -> None:
        items.sort(key=lambda n: (n.sort_order, n.name.lower()))
        for item in items:
            sort_rec(item.children)

    sort_rec(roots)
    return roots


@router.get("", response_model=list[LocationNode])
async def list_locations(
    household_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LocationNode]:
    await require_household_access(session, user, household_id)
    result = await session.scalars(
        select(Location).where(Location.household_id == household_id)
    )
    return _build_tree(list(result.all()))


async def _validate_parent(
    session: AsyncSession, household_id: int, parent_id: int | None, self_id: int | None = None
) -> None:
    if parent_id is None:
        return
    parent = await session.get(Location, parent_id)
    if parent is None or parent.household_id != household_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parent location not found")
    if self_id is not None and parent_id == self_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A location cannot be its own parent")
    # Guard against cycles when re-parenting.
    if self_id is not None:
        loc_map = await get_location_map(session, household_id)
        cursor = parent_id
        while cursor is not None:
            if cursor == self_id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "Cannot move a location under its own descendant"
                )
            cursor = loc_map[cursor].parent_id if cursor in loc_map else None


@router.post("", response_model=LocationOut, status_code=201)
async def create_location(
    household_id: int,
    payload: LocationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Location:
    await require_member(session, user, household_id)
    await _validate_parent(session, household_id, payload.parent_id)
    location = Location(
        household_id=household_id,
        parent_id=payload.parent_id,
        name=payload.name,
        kind=payload.kind,
        sort_order=payload.sort_order,
    )
    session.add(location)
    await session.commit()
    await session.refresh(location)
    return location


async def _get_owned_location(
    session: AsyncSession, household_id: int, location_id: int
) -> Location:
    location = await session.get(Location, location_id)
    if location is None or location.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    return location


@router.patch("/{location_id}", response_model=LocationOut)
async def update_location(
    household_id: int,
    location_id: int,
    payload: LocationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Location:
    await require_member(session, user, household_id)
    location = await _get_owned_location(session, household_id, location_id)
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        await _validate_parent(session, household_id, data["parent_id"], self_id=location_id)
    for field, value in data.items():
        setattr(location, field, value)
    await session.commit()
    await session.refresh(location)
    return location


@router.delete("/{location_id}", status_code=204)
async def delete_location(
    household_id: int,
    location_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await require_member(session, user, household_id)
    location = await _get_owned_location(session, household_id, location_id)
    await session.delete(location)
    await session.commit()
