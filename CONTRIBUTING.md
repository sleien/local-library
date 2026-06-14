# Contributing to Bibliothek

Thanks for your interest in improving Bibliothek. This document describes how to set up a
development environment and the checks your changes should pass.

## Development setup

See the "Development" section of the [README](README.md) for running the backend, the
frontend, and a PostgreSQL instance locally.

## Project layout

- `backend/` - FastAPI application.
  - `app/models/` - SQLAlchemy models (the database schema).
  - `app/schemas/` - Pydantic request and response models.
  - `app/api/` - HTTP routers grouped by resource.
  - `app/services/` - business logic (metadata lookup, covers, search, serialization).
  - `app/migrations/` - Alembic migrations.
  - `tests/` - pytest suite.
- `frontend/` - React + Vite single-page app.

## Before opening a pull request

Run the same checks CI runs:

```sh
# Backend
cd backend
ruff check app tests
pytest

# Frontend
cd frontend
npm run lint
npm run build
```

Guidelines:

- Match the style of the surrounding code.
- Keep endpoints scoped to a household and enforce access through the existing dependencies
  in `app/auth/deps.py`.
- Any change to a model needs an Alembic migration. Generate it with
  `alembic revision --autogenerate -m "describe the change"` and review the result.
- Add or update tests for behaviour you change.
- Prefer small, focused pull requests with a clear description.

## Reporting issues

Open an issue describing what you expected, what happened, and how to reproduce it. Include
your deployment details (Docker image tag or commit) when relevant.
