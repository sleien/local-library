"""ISBN metadata lookup endpoint (used by add and mass-add flows)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import get_current_user
from app.models import User
from app.schemas.book import LookupResult
from app.services.metadata import lookup_isbn

router = APIRouter(prefix="/lookup", tags=["lookup"])


@router.get("/isbn/{isbn}", response_model=LookupResult)
async def lookup(isbn: str, _: User = Depends(get_current_user)) -> LookupResult:
    result = await lookup_isbn(isbn)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No metadata found for that ISBN")
    return result
