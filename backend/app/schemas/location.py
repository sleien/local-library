"""Location tree schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: int | None = None
    kind: str = Field(default="custom", max_length=40)
    sort_order: int = 0


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: int | None = None
    kind: str | None = Field(default=None, max_length=40)
    sort_order: int | None = None


class LocationOut(ORMModel):
    id: int
    household_id: int
    parent_id: int | None
    name: str
    kind: str
    sort_order: int


class LocationNode(LocationOut):
    """A location plus its full path label and children, for tree rendering."""

    path: str
    children: list[LocationNode] = []
