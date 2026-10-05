FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN useradd --create-home app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Image for tests and linting
FROM base AS dev
# Code folder is read-only for the app user, so no lint cache
ENV RUFF_NO_CACHE=true
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
USER app


FROM base AS prod
COPY . .
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
