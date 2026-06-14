"""Block until the database is reachable, then exit.

Run before migrations so the container does not crash when the database host is
not yet resolvable or accepting connections (slow startup, restarts, external DB).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import settings
from app.db import engine

RETRY_INTERVAL_SECONDS = 2
DEFAULT_TIMEOUT_SECONDS = 60


async def _try_connect() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def wait_for_db(timeout: float) -> bool:
    url = make_url(settings.database_url)
    target = f"{url.host}:{url.port or 5432}"
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            await _try_connect()
            print(f"Database is ready at {target}.")
            return True
        except Exception as exc:  # noqa: BLE001 - any connection error means "not ready yet"
            if time.monotonic() >= deadline:
                print(
                    f"Could not reach the database at {target} after {timeout:.0f}s: {exc}",
                    file=sys.stderr,
                )
                return False
            print(f"Waiting for database at {target} (attempt {attempt})...", flush=True)
            await asyncio.sleep(RETRY_INTERVAL_SECONDS)


def main() -> int:
    timeout = float(os.environ.get("DB_WAIT_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))
    ok = asyncio.run(wait_for_db(timeout))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
