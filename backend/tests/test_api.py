"""End-to-end API tests covering the core library and borrowing flows."""

import httpx
from httpx import ASGITransport

from app.main import app
from app.schemas.book import LookupResult


def fresh_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def register(c: httpx.AsyncClient, email: str, name: str = "User") -> int:
    r = await c.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "display_name": name},
    )
    assert r.status_code == 200, r.text
    return r.json()["households"][0]["id"]


def sample_lookup_obj(isbn13="9780134685991", title="Effective Java") -> LookupResult:
    return LookupResult(
        title=title,
        authors=["Joshua Bloch"],
        isbn13=isbn13,
        publisher="Addison-Wesley",
        subjects=["Java", "Programming"],
        covers=[
            {"source": "test", "url": "https://example.com/a.jpg"},
            {"source": "test", "url": "https://example.com/b.jpg"},
        ],
        sources=["test"],
    )


def sample_lookup(isbn13="9780134685991", title="Effective Java"):
    return sample_lookup_obj(isbn13=isbn13, title=title).model_dump()


async def test_auth_flow(client):
    r = await client.post(
        "/api/auth/register",
        json={"email": "a@b.com", "password": "password123", "display_name": "A"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "a@b.com"

    assert (await client.get("/api/auth/me")).status_code == 200
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401

    r = await client.post("/api/auth/login", json={"email": "a@b.com", "password": "password123"})
    assert r.status_code == 200
    r = await client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401


async def test_household_isolation(client):
    await client.post(
        "/api/auth/register",
        json={"email": "u1@b.com", "password": "password123", "display_name": "U1"},
    )
    hid = (await client.get("/api/auth/me")).json()["households"][0]["id"]
    book = await client.post(
        f"/api/households/{hid}/books/from-lookup",
        json={"isbn": "9780134685991", "lookup": sample_lookup()},
    )
    assert book.status_code == 201
    book_id = book.json()["id"]

    # A second user in a different household cannot read the first household.
    await client.post("/api/auth/logout")
    await client.post(
        "/api/auth/register",
        json={"email": "u2@b.com", "password": "password123", "display_name": "U2"},
    )
    assert (await client.get(f"/api/households/{hid}/books/{book_id}")).status_code == 404


async def test_locations_tree(auth_client):
    hid = auth_client.household_id
    office = await auth_client.post(
        f"/api/households/{hid}/locations", json={"name": "Office", "kind": "room"}
    )
    office_id = office.json()["id"]
    shelf = await auth_client.post(
        f"/api/households/{hid}/locations",
        json={"name": "Shelf 1", "kind": "unit", "parent_id": office_id},
    )
    await auth_client.post(
        f"/api/households/{hid}/locations",
        json={"name": "Left", "kind": "section", "parent_id": shelf.json()["id"]},
    )
    tree = (await auth_client.get(f"/api/households/{hid}/locations")).json()
    assert tree[0]["name"] == "Office"
    leaf = tree[0]["children"][0]["children"][0]
    assert leaf["path"] == "Office / Shelf 1 / Left"


async def test_book_creation_covers_tags(auth_client):
    hid = auth_client.household_id
    r = await auth_client.post(
        f"/api/households/{hid}/books/from-lookup",
        json={"isbn": "9780134685991", "lookup": sample_lookup(), "selected_cover_index": 1},
    )
    assert r.status_code == 201
    book = r.json()
    assert book["title"] == "Effective Java"
    assert {t["name"] for t in book["tags"]} >= {"Java", "Programming"}
    assert len(book["covers"]) == 2
    assert book["cover_url"]  # falls back to the selected source URL

    # Adding the same ISBN again reuses the existing book (no duplicate record).
    again = await auth_client.post(
        f"/api/households/{hid}/books/from-lookup",
        json={"isbn": "9780134685991", "lookup": sample_lookup()},
    )
    assert again.status_code == 200
    assert again.json()["id"] == book["id"]


async def test_copies_and_search(auth_client):
    hid = auth_client.household_id
    loc = await auth_client.post(
        f"/api/households/{hid}/locations", json={"name": "Kitchen", "kind": "room"}
    )
    loc_id = loc.json()["id"]
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/from-lookup",
            json={"isbn": "9780134685991", "lookup": sample_lookup()},
        )
    ).json()

    c1 = await auth_client.post(
        f"/api/households/{hid}/books/{book['id']}/copies", json={"location_id": loc_id}
    )
    assert c1.json()["location_path"] == "Kitchen"
    await auth_client.post(f"/api/households/{hid}/books/{book['id']}/copies", json={})

    # Full-text search.
    res = (await auth_client.get(f"/api/search?q=effective&household_id={hid}")).json()
    assert len(res) == 1 and res[0]["copy_count"] == 2

    # Location filter.
    res = (await auth_client.get(f"/api/search?location_id={loc_id}")).json()
    assert len(res) == 1

    # Reading-status filter.
    await auth_client.put(
        f"/api/households/{hid}/books/{book['id']}/status", json={"status": "read", "rating": 5}
    )
    assert len((await auth_client.get("/api/search?status=read")).json()) == 1
    assert len((await auth_client.get("/api/search?status=want")).json()) == 0


async def test_loan_lifecycle(auth_client):
    hid = auth_client.household_id
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/from-lookup",
            json={"isbn": "9780134685991", "lookup": sample_lookup()},
        )
    ).json()
    copy = (
        await auth_client.post(f"/api/households/{hid}/books/{book['id']}/copies", json={})
    ).json()
    person = (
        await auth_client.post(f"/api/households/{hid}/people", json={"name": "Alice"})
    ).json()

    loan = await auth_client.post(
        f"/api/households/{hid}/loans", json={"copy_id": copy["id"], "person_id": person["id"]}
    )
    assert loan.status_code == 201
    loan_id = loan.json()["id"]
    assert loan.json()["is_active"] is True

    # Cannot lend the same copy twice.
    dup = await auth_client.post(
        f"/api/households/{hid}/loans", json={"copy_id": copy["id"], "person_id": person["id"]}
    )
    assert dup.status_code == 409

    # Borrower feedback and return.
    fb = await auth_client.put(
        f"/api/households/{hid}/loans/{loan_id}/feedback", json={"rating": 4, "comment": "Nice"}
    )
    assert fb.json()["rating"] == 4
    ret = await auth_client.post(f"/api/households/{hid}/loans/{loan_id}/return", json={})
    assert ret.json()["is_active"] is False

    # Person view and copy history both show the loan.
    pv = (await auth_client.get(f"/api/households/{hid}/people/{person['id']}/loans")).json()
    assert len(pv) == 1 and pv[0]["feedback"]["comment"] == "Nice"
    ch = (await auth_client.get(f"/api/households/{hid}/copies/{copy['id']}/loans")).json()
    assert len(ch) == 1


async def test_bulk_add(auth_client, monkeypatch):
    from app.api import copies as copies_api

    async def fake_lookup(isbn):
        return LookupResult(title=f"Book {isbn}", isbn13=isbn, sources=["test"])

    monkeypatch.setattr(copies_api, "lookup_isbn", fake_lookup)

    hid = auth_client.household_id
    loc = (
        await auth_client.post(f"/api/households/{hid}/locations", json={"name": "Box"})
    ).json()
    r = await auth_client.post(
        f"/api/households/{hid}/copies/bulk",
        json={"location_id": loc["id"], "isbns": ["9780000000001", "9780000000002"]},
    )
    body = r.json()
    assert body["added"] == 2 and body["failed"] == 0
    # Both books are now searchable in that location.
    res = (await auth_client.get(f"/api/search?location_id={loc['id']}")).json()
    assert len(res) == 2


async def test_friend_sharing(client):
    # User A owns a household with a book.
    hid_a = await register(client, "a@s.com", "A")
    book = (
        await client.post(
            f"/api/households/{hid_a}/books/from-lookup",
            json={"isbn": "9780134685991", "lookup": sample_lookup()},
        )
    ).json()

    async with fresh_client() as b:
        await register(b, "b@s.com", "B")
        # Before sharing, B cannot see A's household at all.
        assert (await b.get(f"/api/households/{hid_a}/books")).status_code == 404

        # A shares read-only with B.
        share = await client.post(f"/api/households/{hid_a}/shares", json={"email": "b@s.com"})
        assert share.status_code == 201

        # B can now read and search A's collection.
        assert (await b.get(f"/api/households/{hid_a}/books")).status_code == 200
        res = (await b.get(f"/api/search?household_id={hid_a}")).json()
        assert len(res) == 1
        me = (await b.get("/api/auth/me")).json()
        assert any(h["id"] == hid_a and h["role"] == "viewer" for h in me["households"])

        # But B cannot modify it: no new copies, no comments.
        assert (
            await b.post(f"/api/households/{hid_a}/books/{book['id']}/copies", json={})
        ).status_code == 404
        assert (
            await b.post(
                f"/api/households/{hid_a}/books/{book['id']}/comments", json={"body": "hi"}
            )
        ).status_code == 404

        # Revoking removes B's access.
        sid = (await client.get(f"/api/households/{hid_a}/shares")).json()[0]["id"]
        assert (await client.delete(f"/api/households/{hid_a}/shares/{sid}")).status_code == 204
        assert (await b.get(f"/api/households/{hid_a}/books")).status_code == 404


async def test_share_requires_existing_user(auth_client):
    hid = auth_client.household_id
    r = await auth_client.post(f"/api/households/{hid}/shares", json={"email": "ghost@s.com"})
    assert r.status_code == 404


async def test_api_tokens(auth_client):
    created = await auth_client.post("/api/tokens", json={"name": "cli"})
    assert created.status_code == 201
    token = created.json()["token"]
    assert token.startswith("blk_")

    # The token authenticates a cookie-less client via Bearer.
    async with fresh_client() as nc:
        me = await nc.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["user"]["email"] == "owner@example.com"

    # Listing never leaks the plaintext.
    listing = (await auth_client.get("/api/tokens")).json()
    assert listing[0]["prefix"] and "token" not in listing[0]

    # Revoked tokens stop working.
    tid = listing[0]["id"]
    assert (await auth_client.delete(f"/api/tokens/{tid}")).status_code == 204
    async with fresh_client() as nc:
        bad = await nc.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert bad.status_code == 401


async def test_user_directory_and_add_member(auth_client):
    hid = auth_client.household_id
    async with fresh_client() as b:
        await register(b, "m2@s.com", "Member Two")
        # Owner can see the user directory and find the new user.
        users = (await auth_client.get("/api/users")).json()
        target = next(u for u in users if u["email"] == "m2@s.com")
        # Before being added, b cannot write to the household.
        assert (
            await b.post(f"/api/households/{hid}/locations", json={"name": "X"})
        ).status_code == 404
        # Owner adds b directly as a member.
        added = await auth_client.post(
            f"/api/households/{hid}/members", json={"user_id": target["id"]}
        )
        assert added.status_code == 201
        # b now has full member access.
        me = (await b.get("/api/auth/me")).json()
        assert any(h["id"] == hid and h["role"] == "member" for h in me["households"])
        assert (
            await b.post(f"/api/households/{hid}/locations", json={"name": "X"})
        ).status_code == 201
        # Adding the same user again conflicts.
        assert (
            await auth_client.post(
                f"/api/households/{hid}/members", json={"user_id": target["id"]}
            )
        ).status_code == 409


async def test_rename_household(auth_client):
    hid = auth_client.household_id
    r = await auth_client.patch(f"/api/households/{hid}", json={"name": "Renamed Library"})
    assert r.status_code == 200 and r.json()["name"] == "Renamed Library"
    households = (await auth_client.get("/api/households")).json()
    assert any(h["id"] == hid and h["name"] == "Renamed Library" for h in households)


async def test_upload_cover(auth_client):
    hid = auth_client.household_id
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/manual", json={"title": "No Cover Book"}
        )
    ).json()
    assert book["cover_url"] is None

    img = b"\x89PNG\r\n\x1a\n" + b"0" * 400  # dummy bytes; > 256 and image/png
    r = await auth_client.post(
        f"/api/households/{hid}/books/{book['id']}/cover",
        files={"file": ("cover.png", img, "image/png")},
    )
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["cover_url"] and detail["cover_url"].startswith("/api/assets/")
    assert any(c["source"] == "upload" and c["selected"] for c in detail["covers"])

    # The stored cover is served back.
    asset_id = detail["cover_url"].rsplit("/", 1)[-1]
    assert (await auth_client.get(f"/api/assets/{asset_id}")).status_code == 200

    # Non-image uploads are rejected.
    bad = await auth_client.post(
        f"/api/households/{hid}/books/{book['id']}/cover",
        files={"file": ("notes.txt", b"definitely not an image " * 20, "text/plain")},
    )
    assert bad.status_code == 400


async def test_refresh_covers(auth_client, monkeypatch):
    from app.api import books as books_api

    async def fake_lookup(isbn):
        return sample_lookup_obj(isbn13=isbn)

    monkeypatch.setattr(books_api, "lookup_isbn", fake_lookup)

    hid = auth_client.household_id
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/manual",
            json={"title": "Single Cover", "isbn13": "9780134685991"},
        )
    ).json()
    assert book["covers"] == []

    r = await auth_client.post(f"/api/households/{hid}/books/{book['id']}/refresh-covers")
    assert r.status_code == 200, r.text
    assert len(r.json()["covers"]) == 2

    # Re-fetching the same covers does not create duplicates.
    again = await auth_client.post(f"/api/households/{hid}/books/{book['id']}/refresh-covers")
    assert len(again.json()["covers"]) == 2

    # A book without an ISBN has nothing to look up.
    no_isbn = (
        await auth_client.post(f"/api/households/{hid}/books/manual", json={"title": "No ISBN"})
    ).json()
    miss = await auth_client.post(f"/api/households/{hid}/books/{no_isbn['id']}/refresh-covers")
    assert miss.status_code == 400


async def test_copy_condition(auth_client):
    hid = auth_client.household_id
    book = (
        await auth_client.post(f"/api/households/{hid}/books/manual", json={"title": "Cond"})
    ).json()

    # A copy can be created with a valid condition grade.
    r = await auth_client.post(
        f"/api/households/{hid}/books/{book['id']}/copies", json={"condition": "good"}
    )
    assert r.status_code == 201, r.text
    copy = r.json()
    assert copy["condition"] == "good"

    # And updated to another valid grade.
    upd = await auth_client.patch(
        f"/api/households/{hid}/copies/{copy['id']}", json={"condition": "like_new"}
    )
    assert upd.status_code == 200
    assert upd.json()["condition"] == "like_new"

    # Unknown grades are rejected.
    bad = await auth_client.post(
        f"/api/households/{hid}/books/{book['id']}/copies", json={"condition": "mint"}
    )
    assert bad.status_code == 422


async def test_reading_log(auth_client):
    hid = auth_client.household_id
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/from-lookup",
            json={"isbn": "9780134685991", "lookup": sample_lookup()},
        )
    ).json()
    await auth_client.put(
        f"/api/households/{hid}/books/{book['id']}/status",
        json={"status": "read", "rating": 5, "finished_at": "2026-01-15"},
    )
    log = (await auth_client.get("/api/reading-log")).json()
    assert len(log) == 1
    assert log[0]["book_id"] == book["id"]
    assert log[0]["finished_at"] == "2026-01-15"
    assert log[0]["rating"] == 5


async def test_lend_to_user(auth_client):
    hid = auth_client.household_id
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/from-lookup",
            json={"isbn": "9780134685991", "lookup": sample_lookup()},
        )
    ).json()
    copy = (
        await auth_client.post(f"/api/households/{hid}/books/{book['id']}/copies", json={})
    ).json()
    async with fresh_client() as b:
        await register(b, "friend@s.com", "Friend")
    friend = next(
        u for u in (await auth_client.get("/api/users")).json() if u["email"] == "friend@s.com"
    )

    # Lend directly to the user -> a linked borrower is created.
    loan = await auth_client.post(
        f"/api/households/{hid}/loans", json={"copy_id": copy["id"], "user_id": friend["id"]}
    )
    assert loan.status_code == 201
    people = (await auth_client.get(f"/api/households/{hid}/people")).json()
    linked = [p for p in people if p["user_id"] == friend["id"]]
    assert len(linked) == 1 and linked[0]["name"] == "Friend"

    # Returning then lending again reuses the same linked borrower (no duplicate).
    await auth_client.post(f"/api/households/{hid}/loans/{loan.json()['id']}/return", json={})
    again = await auth_client.post(
        f"/api/households/{hid}/loans", json={"copy_id": copy["id"], "user_id": friend["id"]}
    )
    assert again.status_code == 201
    people2 = (await auth_client.get(f"/api/households/{hid}/people")).json()
    assert len([p for p in people2 if p["user_id"] == friend["id"]]) == 1

    # Providing neither person_id nor user_id is rejected.
    bad = await auth_client.post(f"/api/households/{hid}/loans", json={"copy_id": copy["id"]})
    assert bad.status_code == 400


async def test_locate(auth_client):
    hid = auth_client.household_id
    office = (
        await auth_client.post(f"/api/households/{hid}/locations", json={"name": "Office"})
    ).json()
    shelf = (
        await auth_client.post(
            f"/api/households/{hid}/locations", json={"name": "Shelf 1", "parent_id": office["id"]}
        )
    ).json()
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/from-lookup",
            json={"isbn": "9780134685991", "lookup": sample_lookup()},
        )
    ).json()
    await auth_client.post(
        f"/api/households/{hid}/books/{book['id']}/copies", json={"location_id": shelf["id"]}
    )

    found = (await auth_client.get(f"/api/households/{hid}/locate?isbn=9780134685991")).json()
    assert found["found"] is True
    assert found["book_id"] == book["id"]
    assert found["copies"][0]["location_path"] == "Office / Shelf 1"

    miss = (await auth_client.get(f"/api/households/{hid}/locate?isbn=9999999999999")).json()
    assert miss["found"] is False


async def test_edit_loan_dates(auth_client):
    hid = auth_client.household_id
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/from-lookup",
            json={"isbn": "9780134685991", "lookup": sample_lookup()},
        )
    ).json()
    copy = (
        await auth_client.post(f"/api/households/{hid}/books/{book['id']}/copies", json={})
    ).json()
    person = (
        await auth_client.post(f"/api/households/{hid}/people", json={"name": "Alice"})
    ).json()
    loan = (
        await auth_client.post(
            f"/api/households/{hid}/loans", json={"copy_id": copy["id"], "person_id": person["id"]}
        )
    ).json()

    # Set a specific return date.
    r = await auth_client.patch(
        f"/api/households/{hid}/loans/{loan['id']}",
        json={"returned_at": "2026-02-01T00:00:00Z"},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert r.json()["returned_at"].startswith("2026-02-01")

    # Clearing it reopens the loan.
    r2 = await auth_client.patch(
        f"/api/households/{hid}/loans/{loan['id']}", json={"returned_at": None}
    )
    assert r2.json()["is_active"] is True
    assert r2.json()["returned_at"] is None


async def test_export_csv(auth_client):
    hid = auth_client.household_id
    loc = (
        await auth_client.post(f"/api/households/{hid}/locations", json={"name": "Office"})
    ).json()
    book = (
        await auth_client.post(
            f"/api/households/{hid}/books/from-lookup",
            json={"isbn": "9780134685991", "lookup": sample_lookup()},
        )
    ).json()
    await auth_client.post(
        f"/api/households/{hid}/books/{book['id']}/copies", json={"location_id": loc["id"]}
    )
    r = await auth_client.get(f"/api/households/{hid}/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.text
    assert "ISBN13" in body
    assert "9780134685991" in body
    assert "Effective Java" in body
    assert "Office" in body


def test_isbn_conversion():
    from app.services.metadata import isbn10_to_isbn13, isbn13_to_isbn10

    assert isbn10_to_isbn13("3150097622") == "9783150097625"
    assert isbn13_to_isbn10("9783150097625") == "3150097622"
    # Non-978 ISBN-13 has no ISBN-10 equivalent.
    assert isbn13_to_isbn10("9791234567896") is None
