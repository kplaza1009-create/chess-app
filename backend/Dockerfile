FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd --system chess && useradd --system --gid chess --home-dir /app chess
COPY requirements.lock ./
RUN pip install --no-deps -r requirements.lock
COPY --chown=chess:chess . .
USER chess
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]

FROM base AS development
USER root
RUN pip install --no-deps -r requirements-dev.lock
USER chess

FROM base AS production
