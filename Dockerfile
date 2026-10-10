FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/

ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.13-slim

ENV TZ=Europe/Moscow
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"
ENV DB_DIR=/data
ENV LOG_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --system --no-create-home --uid 10001 app && \
    mkdir /data && chown app:app /data

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .

USER app
CMD ["python", "-u", "bot/main.py"]
