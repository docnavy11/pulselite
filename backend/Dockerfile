# ── Base: shared between dev and prod ────────────────────────────
FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv

# ── Dev: includes test tools, Playwright, dev deps ───────────────
FROM base AS dev
COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"
RUN playwright install chromium --with-deps
COPY . .

# ── Production: minimal, no dev deps ─────────────────────────────
FROM base AS prod
COPY pyproject.toml .
RUN uv pip install --system -e "."
RUN playwright install chromium --with-deps
COPY . .
RUN useradd -r -s /bin/false appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:combined_app", "--host", "0.0.0.0", "--port", "8000"]
