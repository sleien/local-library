#!/usr/bin/env sh
set -e

# Wait for the database to accept connections before migrating, so a slow or
# late-starting database does not crash the container on boot.
echo "Waiting for database..."
python -m app.db_wait

# Apply database migrations, then start the server.
echo "Running database migrations..."
alembic upgrade head

echo "Starting Bibliothek on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
