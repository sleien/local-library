# Bibliothek

Bibliothek is a self-hosted web application for cataloguing a personal or household
book collection. It keeps track of where every physical copy lives, what you have read,
how you rated it, and the full history of who borrowed what and when. It is built to run
on your own hardware with Docker, works on phones and desktops, and exposes a documented
REST API so you can automate or integrate it.

The name is German for "library".

## Features

- Add books by ISBN or by scanning a barcode with your device camera. Metadata and cover
  images are pulled automatically from Open Library and Google Books.
- When several cover images are found, you choose the correct one — or upload your own.
- Track multiple physical copies of the same title. Each copy has its own location and its
  own borrowing history, so the same book can sit on two shelves or be lent out while another
  copy stays home.
- Organise copies with a location hierarchy you define yourself, for example
  "Office Shelf 1 / Section 3 / Left". Nothing about the structure is hardcoded.
- Per-user reading status (want to read, reading, read), star ratings, and personal reviews.
- Household comments on a book, separate from personal reviews.
- Tags: subjects from the online catalogue are added automatically, and you can add your own.
  Everything is filterable.
- Lending: save the people you lend to, record loans with optional due dates, mark returns,
  and capture the borrower's rating and comment. View it from the book ("who has had this")
  or from the person ("which books they have had, and when").
- Mass add: pick a location, scan a stack of barcodes in a row, and add them all at once.
- Full-text search across titles, authors, ISBNs and descriptions, with filters for tags,
  location, read status, and availability.
- Multiple users per household with full shared read and write access (for example, you and
  your partner). Invite others with a link.
- Share a library read-only with friends in other households: they can browse and search your
  books but cannot change anything.
- An interactive onboarding tour for new users, with a skip button.
- Responsive interface for mobile and desktop, with light and dark themes.
- A complete REST API with interactive documentation at `/api/docs`, plus personal API tokens
  for scripts and integrations.

## Screenshots

Screenshots live in `docs/screenshots/` (add your own once deployed).

## Quick start

You need Docker and the Docker Compose plugin.

```sh
git clone https://github.com/sleien/local-library.git
cd local-library
cp .env.example .env
# Edit .env and set a strong SECRET_KEY, for example:
#   SECRET_KEY=$(openssl rand -hex 32)
docker compose up -d
```

The application is then available at http://localhost:8000. The first account you register
becomes the owner of a new household. Open the API documentation at
http://localhost:8000/api/docs.

The Compose file builds the image from this repository. To run a prebuilt image from the
GitHub Container Registry instead, set `IMAGE` in your `.env` (for example
`IMAGE=ghcr.io/sleien/local-library:latest`) and remove or comment the `build:` line in
`docker-compose.yml`.

## Configuration

All configuration is through environment variables (read from `.env` by Compose).

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | (required) | Secret used to sign auth tokens. Use a long random value. |
| `PUBLIC_URL` | `http://localhost:8000` | Public base URL, used for OIDC redirects and invite links. |
| `PORT` | `8000` | Host port the app is published on. |
| `COOKIE_SECURE` | `false` | Set to `true` when serving over HTTPS. |
| `ALLOW_REGISTRATION` | `true` | When `false`, accounts can only be created through an invite. |
| `POSTGRES_USER` | `bibliothek` | Database user. |
| `POSTGRES_PASSWORD` | `bibliothek` | Database password. |
| `POSTGRES_DB` | `bibliothek` | Database name. |
| `OIDC_ENABLED` | `false` | Enable Authentik / OpenID Connect single sign-on. |
| `OIDC_ISSUER` | | OIDC issuer URL from your provider. |
| `OIDC_CLIENT_ID` | | OIDC client id. |
| `OIDC_CLIENT_SECRET` | | OIDC client secret. |
| `OIDC_DISPLAY_NAME` | `Authentik` | Label shown on the single sign-on button. |

Book covers and other uploads are stored on the `app-data` volume (mounted at `/data`).
The database is stored on the `db-data` volume.

## Authentik (OpenID Connect)

Local accounts work out of the box. To add single sign-on with Authentik:

1. In Authentik, create an OAuth2/OpenID Provider and an Application for Bibliothek.
2. Set the redirect URI to `${PUBLIC_URL}/api/auth/oidc/callback`.
3. Copy the issuer URL (it ends in `/application/o/<slug>/`), the client id, and the client
   secret into your `.env`:

   ```sh
   OIDC_ENABLED=true
   OIDC_ISSUER=https://authentik.example.com/application/o/bibliothek/
   OIDC_CLIENT_ID=...
   OIDC_CLIENT_SECRET=...
   ```

4. Restart with `docker compose up -d`.

A "Continue with Authentik" button then appears on the sign-in screen. On first sign-in a
new user is created and matched to any existing local account with the same email address.

## Users and households

A household owns a collection. Everyone in a household has full read and write access.

- The first registered user creates a household and becomes its owner.
- Owners can invite others from Settings. Sharing the generated invite link lets someone
  register straight into the household (handy for a partner).
- A user can belong to several households and switch between them from the header.

You can also share a library read-only with a friend: in Settings, enter the email of another
registered user under "Read-only sharing". They can then browse and search your collection from
their own account (it appears in their library switcher) but cannot add, edit, move, or lend
anything. Revoke access at any time.

## Using the API

The backend is the same REST API the web interface uses. Interactive documentation is served
at `/api/docs` and the OpenAPI schema at `/api/openapi.json`.

For scripts and integrations, create a personal API token in Settings under "API access" and send
it as a bearer token:

```sh
# List books in household 1 using a personal API token.
curl -s -H "Authorization: Bearer blk_your_token_here" \
  http://localhost:8000/api/households/1/books

# Look up an ISBN.
curl -s -H "Authorization: Bearer blk_your_token_here" \
  http://localhost:8000/api/lookup/isbn/9780134685991
```

The browser interface authenticates with a session cookie instead, so you can also drive the API
by signing in (`POST /api/auth/login`) and reusing the cookie.

## Development

The backend is FastAPI (Python) and the frontend is React with Vite. PostgreSQL is required.

Start a database:

```sh
docker run -d --name bibliothek-pg -p 5432:5432 \
  -e POSTGRES_USER=bibliothek -e POSTGRES_PASSWORD=bibliothek -e POSTGRES_DB=bibliothek \
  postgres:16
```

Backend:

```sh
cd backend
python -m venv .venv && . .venv/bin/activate   # or use uv
pip install -e ".[dev]"
export SECRET_KEY=dev-secret
export DATABASE_URL=postgresql+asyncpg://bibliothek:bibliothek@localhost:5432/bibliothek
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Frontend (proxies API calls to the backend):

```sh
cd frontend
npm install
npm run dev   # http://localhost:5173
```

Tests and linting:

```sh
# Backend (needs a database; uses bibliothek_test by default)
cd backend && pytest && ruff check app tests

# Frontend
cd frontend && npm run lint && npm run build
```

After changing a model, generate a migration with
`alembic revision --autogenerate -m "describe change"` and review it before committing.

## Architecture

- A single Docker image. A multi-stage build compiles the React app, then a FastAPI process
  serves both the API under `/api` and the static frontend for everything else.
- PostgreSQL stores the data; full-text search uses a `tsvector` column with a GIN index.
- The bibliographic record (a book) is separate from physical copies, which is what makes
  multiple copies, per-copy locations, and per-copy lending histories possible.
- Cover images are downloaded to the data volume and served through an access-controlled
  endpoint.
- Authentication uses signed tokens in HTTP-only cookies; optional OIDC is handled with
  Authlib.

```
bibliothek/
  backend/    FastAPI app, models, migrations, tests
  frontend/   React + Vite single-page app
  Dockerfile  multi-stage build (frontend then backend)
  docker-compose.yml
```

## Roadmap

Implemented:

- Core library: books, copies, locations, ISBN and barcode adding, cover selection, tags,
  search and filters, reading status, ratings, comments.
- Borrowing: people, loans, history, borrower feedback, book and person views, mass add.
- Local accounts and optional Authentik single sign-on, households and invites.
- Read-only sharing of a collection with friends in other households.
- Personal API tokens for programmatic access without a browser session.
- An interactive onboarding tour with a skip option.

Planned:

- An isometric shelf map: upload a drawing of your shelves and highlight where a book sits.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). In short: keep the backend
`ruff`-clean with passing `pytest`, keep the frontend `eslint`-clean and building, and include
a migration for any schema change.

## License

Released under the MIT License. See [LICENSE](LICENSE).
