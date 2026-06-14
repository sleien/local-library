# syntax=docker/dockerfile:1

# --- Stage 1: build the React single-page app ---
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime serving the API and the built SPA ---
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIR=/app/static \
    DATA_DIR=/data \
    PORT=8000

WORKDIR /app/backend

# Application code, migrations, and project metadata.
COPY backend/ ./
RUN pip install --upgrade pip && pip install . && chmod +x entrypoint.sh

# Built frontend from stage 1.
COPY --from=frontend /build/dist /app/static

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
