"""FastAPI application factory.

Serves the REST API under /api (with OpenAPI docs at /api/docs) and the built
React single-page app for every other route.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api import api_router
from app.config import settings

# Directory containing the compiled frontend (populated in the Docker image).
_STATIC_DIR = os.environ.get("FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "static"))


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Self-hosted book collection manager.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Signed session cookie, used only for the OIDC handshake state/nonce.
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax")

    app.include_router(api_router)

    @app.get("/api/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    _mount_spa(app)
    return app


def _mount_spa(app: FastAPI) -> None:
    """Serve the SPA assets and fall back to index.html for client-side routes."""
    index_file = os.path.join(_STATIC_DIR, "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = os.path.join(_STATIC_DIR, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return JSONResponse(
            {"detail": "Frontend not built. Run the dev server or build the image."},
            status_code=404,
        )


app = create_app()
