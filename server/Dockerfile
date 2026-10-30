# Build from the repo root: docker build -f server/Dockerfile .
FROM python:3.14.8-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY server/ server/
COPY db/ db/
RUN uv sync --frozen --no-dev

RUN useradd -m appuser
USER appuser

ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app/server/src

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$SPANPORT_SERVER_PORT/health')"

CMD ["python", "-m", "spanport_server"]
