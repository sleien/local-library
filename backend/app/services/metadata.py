"""ISBN metadata lookup across pluggable providers (Open Library, Google Books).

Each provider returns a partial LookupResult; results are merged into one,
collecting every cover image so the user can pick the correct one.
"""

from __future__ import annotations

import re

import httpx

from app.config import settings
from app.schemas.book import LookupCover, LookupResult

_TIMEOUT = httpx.Timeout(10.0)


def normalize_isbn(raw: str) -> str:
    """Strip everything but digits and a trailing X (ISBN-10 check char)."""
    return re.sub(r"[^0-9Xx]", "", raw).upper()


class MetadataProvider:
    name = "base"

    async def lookup(self, client: httpx.AsyncClient, isbn: str) -> LookupResult | None:
        raise NotImplementedError


class OpenLibraryProvider(MetadataProvider):
    name = "openlibrary"

    async def lookup(self, client: httpx.AsyncClient, isbn: str) -> LookupResult | None:
        record = await self._fetch_data(client, isbn)
        doc = await self._fetch_search(client, isbn)
        if not record and not doc:
            return None
        record = record or {}

        covers: list[LookupCover] = []
        # A cover keyed by Open Library's internal id (from search) is a real
        # image when present; the ISBN-keyed endpoint often returns a blank
        # placeholder, so we no longer use it.
        cover_i = (doc or {}).get("cover_i")
        if cover_i:
            covers.append(
                LookupCover(source=self.name, url=f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg")
            )
        cover_map = record.get("cover") or {}
        for url_value in (cover_map.get("large"), cover_map.get("medium")):
            if url_value:
                covers.append(LookupCover(source=self.name, url=url_value))

        identifiers = record.get("identifiers") or {}
        authors = [a.get("name") for a in record.get("authors", []) if a.get("name")]
        if not authors and doc:
            authors = doc.get("author_name", [])
        publisher = ", ".join(
            p.get("name") for p in record.get("publishers", []) if p.get("name")
        ) or None
        if not publisher and doc and doc.get("publisher"):
            publisher = doc["publisher"][0]
        published_date = record.get("publish_date")
        if not published_date and doc and doc.get("first_publish_year"):
            published_date = str(doc["first_publish_year"])

        return LookupResult(
            title=record.get("title") or (doc or {}).get("title") or "Unknown title",
            subtitle=record.get("subtitle"),
            authors=authors,
            isbn10=(identifiers.get("isbn_10") or [None])[0],
            isbn13=(identifiers.get("isbn_13") or [None])[0],
            publisher=publisher,
            published_date=published_date,
            page_count=record.get("number_of_pages")
            or ((doc or {}).get("number_of_pages_median")),
            subjects=[s.get("name") for s in record.get("subjects", []) if s.get("name")][:12],
            covers=covers,
            sources=[self.name],
        )

    async def _fetch_data(self, client: httpx.AsyncClient, isbn: str) -> dict | None:
        try:
            resp = await client.get(
                "https://openlibrary.org/api/books",
                params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            )
            resp.raise_for_status()
            return resp.json().get(f"ISBN:{isbn}")
        except (httpx.HTTPError, ValueError):
            return None

    async def _fetch_search(self, client: httpx.AsyncClient, isbn: str) -> dict | None:
        try:
            resp = await client.get(
                "https://openlibrary.org/search.json",
                params={
                    "isbn": isbn,
                    "fields": "title,author_name,cover_i,first_publish_year,"
                    "publisher,number_of_pages_median",
                    "limit": 1,
                },
            )
            resp.raise_for_status()
            docs = resp.json().get("docs") or []
            return docs[0] if docs else None
        except (httpx.HTTPError, ValueError):
            return None


class GoogleBooksProvider(MetadataProvider):
    name = "googlebooks"

    async def lookup(self, client: httpx.AsyncClient, isbn: str) -> LookupResult | None:
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {"q": f"isbn:{isbn}", "country": "US"}
        # An API key lifts the low anonymous quota that otherwise returns HTTP 429.
        if settings.google_books_api_key:
            params["key"] = settings.google_books_api_key
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return None
        items = data.get("items") or []
        if not items:
            return None
        info = items[0].get("volumeInfo", {})

        isbn10 = isbn13 = None
        for ident in info.get("industryIdentifiers", []):
            if ident.get("type") == "ISBN_10":
                isbn10 = ident.get("identifier")
            elif ident.get("type") == "ISBN_13":
                isbn13 = ident.get("identifier")

        covers: list[LookupCover] = []
        for key in ("extraLarge", "large", "medium", "thumbnail", "smallThumbnail"):
            link = (info.get("imageLinks") or {}).get(key)
            if link:
                covers.append(LookupCover(source=self.name, url=link.replace("http://", "https://")))

        return LookupResult(
            title=info.get("title") or "Unknown title",
            subtitle=info.get("subtitle"),
            authors=info.get("authors", []),
            isbn10=isbn10,
            isbn13=isbn13,
            publisher=info.get("publisher"),
            published_date=info.get("publishedDate"),
            page_count=info.get("pageCount"),
            language=info.get("language"),
            description=info.get("description"),
            subjects=info.get("categories", [])[:12],
            covers=covers,
            sources=[self.name],
        )


PROVIDERS: list[MetadataProvider] = [OpenLibraryProvider(), GoogleBooksProvider()]


def _merge(base: LookupResult, other: LookupResult) -> LookupResult:
    """Fill gaps in base from other; union authors, subjects, covers, sources."""

    def pick(a, b):
        return a if a else b

    base.title = base.title if base.title != "Unknown title" else other.title
    base.subtitle = pick(base.subtitle, other.subtitle)
    base.isbn10 = pick(base.isbn10, other.isbn10)
    base.isbn13 = pick(base.isbn13, other.isbn13)
    base.publisher = pick(base.publisher, other.publisher)
    base.published_date = pick(base.published_date, other.published_date)
    base.page_count = pick(base.page_count, other.page_count)
    base.language = pick(base.language, other.language)
    base.description = pick(base.description, other.description)
    base.authors = base.authors or other.authors
    base.subjects = list(dict.fromkeys([*base.subjects, *other.subjects]))
    base.sources = list(dict.fromkeys([*base.sources, *other.sources]))

    seen = {c.url for c in base.covers}
    for cover in other.covers:
        if cover.url not in seen:
            base.covers.append(cover)
            seen.add(cover.url)
    return base


async def lookup_isbn(isbn: str) -> LookupResult | None:
    """Query all providers and merge into a single normalised result."""
    isbn = normalize_isbn(isbn)
    if not isbn:
        return None
    merged: LookupResult | None = None
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        for provider in PROVIDERS:
            result = await provider.lookup(client, isbn)
            if result is None:
                continue
            merged = result if merged is None else _merge(merged, result)
    if merged and not (merged.isbn13 or merged.isbn10):
        # Fall back to the queried ISBN.
        if len(isbn) == 13:
            merged.isbn13 = isbn
        elif len(isbn) == 10:
            merged.isbn10 = isbn
    return merged
