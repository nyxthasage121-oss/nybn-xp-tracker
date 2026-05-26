"""Shared async SQLAlchemy engine for Enoch.

Connects to the same SQLite database as the Flask web app, defaulting to
the path Flask resolves when DATABASE_URL is unset (sqlite:///data/db.sqlite
relative to apps/web/).
"""

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_engine: AsyncEngine | None = None


def _build_url() -> str:
    """Construct the async (aiosqlite) database URL from environment variables."""
    raw = os.getenv("DATABASE_URL", "")

    if raw.startswith("sqlite+aiosqlite://"):
        # Already an async URL — use as-is.
        return raw

    if raw.startswith("sqlite:///"):
        # Convert pysqlite URL → aiosqlite, resolving relative paths the same
        # way apps/web/config.py does (relative to apps/web/).
        rel = raw[len("sqlite:///"):]
        if rel.startswith("/"):
            abs_path = rel
        else:
            web_dir = Path(__file__).resolve().parents[2] / "web"
            abs_path = str(web_dir / rel)
        return f"sqlite+aiosqlite:///{abs_path}"

    # Default: match Flask's default (data/db.sqlite relative to apps/web)
    web_dir = Path(__file__).resolve().parents[2] / "web"
    abs_path = str(web_dir / "data" / "db.sqlite")
    return f"sqlite+aiosqlite:///{abs_path}"


def get_engine() -> AsyncEngine:
    """Return the shared async engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(_build_url(), echo=False)
    return _engine
