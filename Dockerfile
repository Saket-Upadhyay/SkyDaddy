FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY app.py ./
COPY templates/ templates/
COPY static/ static/

EXPOSE 8000

CMD ["uv", "run", "prod"]
