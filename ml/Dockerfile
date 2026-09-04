FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install deps before copying source so this layer only rebuilds when
# pyproject.toml/uv.lock change, not on every source edit.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

RUN uv sync --frozen --no-dev

EXPOSE 8001

# Railway assigns a dynamic $PORT; ml/'s own default (config.py) is 8001.
CMD ["sh", "-c", "uv run uvicorn ml.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
