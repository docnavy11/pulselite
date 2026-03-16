# ── Base: shared between all targets ─────────────────────────────
FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv

# ── Dev: all deps (API + worker + test), Playwright ──────────────
FROM base AS dev
COPY pyproject.toml .
# CPU-only PyTorch — saves ~6GB by excluding CUDA/nvidia/triton
RUN uv pip install --system \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match \
    -e ".[worker,dev]" \
    && rm -rf /root/.cache/pip /root/.cache/uv /tmp/*
RUN playwright install chromium --with-deps
COPY . .

# ── API: lean image — no torch, no bertopic, no playwright ──────
FROM base AS api
COPY pyproject.toml .
RUN uv pip install --system -e "." \
    && rm -rf /root/.cache/pip /root/.cache/uv /tmp/*
# Remove build tools not needed at runtime
RUN apt-get purge -y gcc g++ build-essential && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN useradd -r -s /bin/false appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:combined_app", "--host", "0.0.0.0", "--port", "8000"]

# ── Worker: full deps + Playwright for crawling ─────────────────
FROM base AS worker
COPY pyproject.toml .
RUN uv pip install --system \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match \
    -e ".[worker]" \
    && rm -rf /root/.cache/pip /root/.cache/uv /tmp/*
RUN playwright install chromium --with-deps
# Remove build tools not needed at runtime
RUN apt-get purge -y gcc g++ build-essential && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN useradd -r -s /bin/false appuser
USER appuser
CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info"]
