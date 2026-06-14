"""Aggregate API router mounted under /api."""

from fastapi import APIRouter

from app.api import (
    assets,
    auth,
    books,
    copies,
    households,
    loans,
    locations,
    lookup,
    people,
    search,
    tags,
    tokens,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(households.router)
api_router.include_router(locations.router)
api_router.include_router(lookup.router)
api_router.include_router(books.router)
api_router.include_router(copies.router)
api_router.include_router(tags.router)
api_router.include_router(people.router)
api_router.include_router(loans.router)
api_router.include_router(search.router)
api_router.include_router(assets.router)
api_router.include_router(tokens.router)
