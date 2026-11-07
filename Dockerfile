# AlwaysON API (phase 2). Build: docker build -t alwayson-api .   Run: docker run -p 8000:8000 alwayson-api
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app

# dependencies first (cached layer)
COPY pyproject.toml uv.lock .python-version README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# code and the small data the API reads (raw downloads are not needed)
COPY api ./api
COPY scripts/utils.py ./scripts/utils.py
COPY data/processed ./data/processed
COPY data/demo ./data/demo
COPY data/samples ./data/samples

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-sync uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
