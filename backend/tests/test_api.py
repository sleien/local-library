"""End-to-end API tests covering the core library and borrowing flows."""

from app.schemas.book import LookupResult


def sample_lookup(isbn13="9780134685991", title="Effective Java"):
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
    ).model_dump()


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
