# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Data location: on OpenHost, OPENHOST_APP_DATA_DIR is injected and used; for a
# plain `docker run`, config falls back to /app/instance (mount a volume there).

# Install the library + web extra (includes gunicorn). Copy only what the build
# needs first so the dependency layer is cached across source-only changes.
COPY pyproject.toml README.md ./
COPY src ./src
COPY webapp ./webapp
RUN pip install ".[web]"

# Run as a non-root user; pre-create the instance dir so a fresh named volume
# mounted there inherits writable ownership.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/instance \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/v1/metrics').status==200 else 1)"

# Gunicorn calls the application factory. A long timeout covers synchronous
# renders that fetch many map tiles on first view.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "webapp:create_app()"]
