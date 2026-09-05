FROM python:3.12-slim

# Stockfish itself, for "My Games" blunder detection — not a Python package,
# just a compiled engine binary. Debian's package installs it to /usr/games,
# which isn't on $PATH for a non-login shell — symlink it onto a directory
# that is, so config.py's "stockfish" default (bare command, no path) works.
RUN apt-get update && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/games/stockfish /usr/local/bin/stockfish

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
