#!/usr/bin/env sh
set -e

# Apply database migrations, then start the server.
echo "Running database migrations..."
alembic upgrade head

echo "Starting Bibliothek on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
