FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# main.py is the entry-point module — copy with metadata so setuptools
# can build the project scripts before copying the rest of the app
COPY pyproject.toml uv.lock main.py ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY app.py ./
COPY templates/ templates/
COPY static/ static/

EXPOSE 8080

CMD ["uv", "run", "prod"]
