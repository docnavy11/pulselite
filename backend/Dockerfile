FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"
RUN playwright install chromium --with-deps
COPY . .
