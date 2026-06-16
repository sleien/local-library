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


def isbn10_to_isbn13(isbn10: str) -> str | None:
    if len(isbn10) != 10 or not isbn10[:9].isdigit():
        return None
    core = "978" + isbn10[:9]
    total = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(core))
    return core + str((10 - total % 10) % 10)


def isbn13_to_isbn10(isbn13: str) -> str | None:
    if len(isbn13) != 13 or not isbn13.startswith("978") or not isbn13.isdigit():
        return None
    core = isbn13[3:12]
    total = sum((10 - i) * int(c) for i, c in enumerate(core))
    check = (11 - total % 11) % 11
    return core + ("X" if check == 10 else str(check))


def isbn_variants(scanned: str) -> tuple[str | None, str | None]:
    """Return (isbn10, isbn13) for a scanned ISBN, deriving the missing form so a
    book is matched whichever barcode form was stored or scanned."""
    norm = normalize_isbn(scanned)
    if len(norm) == 13:
        return isbn13_to_isbn10(norm), norm
    if len(norm) == 10:
        return norm, isbn10_to_isbn13(norm)
    return None, None


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
        # image when present; the bare ISBN endpoint returns a blank placeholder
        # for missing covers, so only fall back to it (with default=false, which
        # 404s instead of serving the placeholder) when nothing else turned up.
        cover_i = (doc or {}).get("cover_i")
        if cover_i:
            covers.append(
                LookupCover(source=self.name, url=f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg")
            )
        cover_map = record.get("cover") or {}
        for url_value in (cover_map.get("large"), cover_map.get("medium")):
            if url_value:
                covers.append(LookupCover(source=self.name, url=url_value))
        if not cover_i and not cover_map:
            covers.append(
                LookupCover(
                    source=self.name,
                    url=f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false",
                )
            )

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


class AppleBooksProvider(MetadataProvider):
    """Apple Books via the public iTunes lookup API (no key required).

    Covers here are the store artwork, which is often the exact edition cover
    that Open Library / Google Books miss for popular titles."""

    name = "applebooks"

    async def lookup(self, client: httpx.AsyncClient, isbn: str) -> LookupResult | None:
        try:
            resp = await client.get(
                "https://itunes.apple.com/lookup",
                params={"isbn": isbn, "entity": "ebook"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return None
        results = data.get("results") or []
        if not results:
            return None
        item = results[0]

        covers: list[LookupCover] = []
        art = item.get("artworkUrl100")
        if art:
            # Artwork URLs end in ".../100x100bb.jpg"; ask for a larger box.
            covers.append(LookupCover(source=self.name, url=art.replace("100x100bb", "600x600bb")))

        description = item.get("description")
        if description:
            # Apple returns HTML in the description; strip tags for a clean blurb.
            description = re.sub(r"<[^>]+>", "", description).strip() or None

        release = item.get("releaseDate")
        # Leave ISBNs unset: the matched edition may differ from the scanned one,
        # and lookup_isbn records/derives the scanned ISBN itself.
        return LookupResult(
            title=item.get("trackName") or "Unknown title",
            authors=[item["artistName"]] if item.get("artistName") else [],
            published_date=release[:10] if release else None,
            description=description,
            subjects=[item["primaryGenreName"]] if item.get("primaryGenreName") else [],
            covers=covers,
            sources=[self.name],
        )


PROVIDERS: list[MetadataProvider] = [
    OpenLibraryProvider(),
    GoogleBooksProvider(),
    AppleBooksProvider(),
]


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
    if merged:
        # Always record the scanned ISBN, even if the provider only returned the
        # other form, then derive the missing form so either barcode matches.
        if len(isbn) == 13 and not merged.isbn13:
            merged.isbn13 = isbn
        elif len(isbn) == 10 and not merged.isbn10:
            merged.isbn10 = isbn
        if merged.isbn13 and not merged.isbn10:
            merged.isbn10 = isbn13_to_isbn10(merged.isbn13)
        if merged.isbn10 and not merged.isbn13:
            merged.isbn13 = isbn10_to_isbn13(merged.isbn10)
    return merged
