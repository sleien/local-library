"""Pytest fixtures: a clean schema per test and an ASGI HTTP client.

Tests run against PostgreSQL (the app relies on tsvector full-text search).
Point DATABASE_URL at a disposable test database before running.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://bibliothek:bibliothek@localhost:5432/bibliothek_test",
)
# Each test runs on its own event loop; disable pooling to avoid reusing
# asyncpg connections bound to a closed loop.
os.environ["DB_DISABLE_POOL"] = "true"

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import books as books_service  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Rebuild the schema before each test so model changes are always reflected.

    Drops the whole schema (avoids constraint-name issues with the circular
    book<->cover_candidate FK) and recreates all tables from the models.
    """
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP SCHEMA public CASCADE")
        await conn.exec_driver_sql("CREATE SCHEMA public")
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
def no_cover_downloads(monkeypatch):
    """Avoid hitting the network for cover images during tests."""

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(books_service, "download_cover", _noop)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_client(client):
    """A client registered as a fresh user, with their first household id."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "password123",
            "display_name": "Owner",
            "household_name": "Test Library",
        },
    )
    assert resp.status_code == 200, resp.text
    household_id = resp.json()["households"][0]["id"]
    client.household_id = household_id  # type: ignore[attr-defined]
    return client
