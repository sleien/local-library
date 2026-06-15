"""Export a library as CSV (one row per book, including ISBNs for re-import)."""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, require_household_access
from app.db import get_session
from app.models import Book, Household, User
from app.services.locations import build_path, get_location_map

router = APIRouter(prefix="/households/{household_id}", tags=["export"])

_COLUMNS = [
    "ISBN13",
    "ISBN10",
    "Title",
    "Subtitle",
    "Authors",
    "Publisher",
    "Published",
    "Tags",
    "Copies",
    "Locations",
]


@router.get("/export")
async def export_library(
    household_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await require_household_access(session, user, household_id)
    household = await session.get(Household, household_id)
    books = (
        await session.scalars(
            select(Book)
            .where(Book.household_id == household_id)
            .order_by(Book.title)
            .options(selectinload(Book.copies), selectinload(Book.tags))
        )
    ).all()
    loc_map = await get_location_map(session, household_id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_COLUMNS)
    for book in books:
        locations = sorted(
            {build_path(loc_map, c.location_id) for c in book.copies if c.location_id}
        )
        writer.writerow(
            [
                book.isbn13 or "",
                book.isbn10 or "",
                book.title,
                book.subtitle or "",
                "; ".join(book.authors or []),
                book.publisher or "",
                book.published_date or "",
                "; ".join(t.name for t in book.tags),
                len(book.copies),
                "; ".join(locations),
            ]
        )

    name = household.name if household else "library"
    raw = f"bibliothek-{name}-{date.today().isoformat()}.csv"
    safe = "".join(c if (c.isalnum() or c in "-_.") else "-" for c in raw)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )
