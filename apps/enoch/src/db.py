"""Shared database state for Enoch.

The structured models (VChar, VGuild, VUser, RPPost) now live in SQLite via
async SQLAlchemy (see storage.py). The raw MongoDB collections below are
stubbed out — they return no-ops until each feature is ported to SQLite.
"""

from loguru import logger

import storage


# ---------------------------------------------------------------------------
# Stub collection — no-op stand-in for raw MongoDB collections
# ---------------------------------------------------------------------------

class _EmptyAsyncCursor:
    """An empty async cursor that also works as a context manager."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    async def to_list(self, *args, **kwargs):
        return []


class _StubCollection:
    """A no-op stub for raw MongoDB collection calls.

    Every method either returns None/empty or does nothing.  Code that
    previously wrote to or read from MongoDB will silently no-op until the
    relevant feature is ported to SQLite.
    """

    async def find_one(self, *args, **kwargs):
        return None

    async def find_one_and_update(self, *args, **kwargs):
        return None

    async def insert_one(self, *args, **kwargs):
        pass

    async def update_one(self, *args, **kwargs):
        pass

    async def update_many(self, *args, **kwargs):
        pass

    async def delete_one(self, *args, **kwargs):
        pass

    async def delete_many(self, *args, **kwargs):
        pass

    async def bulk_write(self, *args, **kwargs):
        pass

    def find(self, *args, **kwargs):
        return _EmptyAsyncCursor()

    async def aggregate(self, *args, **kwargs):
        return _EmptyAsyncCursor()


# Stub collections for MongoDB-only features not yet ported to SQLite.
command_log = _StubCollection()
headers = _StubCollection()
interactions = _StubCollection()
log = _StubCollection()
probabilities = _StubCollection()
rolls = _StubCollection()
rp_posts = _StubCollection()
supporters = _StubCollection()
upload_log = _StubCollection()


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

async def init():
    """Initialize the database engine (creates it on first use)."""
    _ = storage.get_engine()
    logger.info("Initialized SQLAlchemy engine")


async def close():
    """Dispose the async engine and close all pooled connections."""
    engine = storage.get_engine()
    await engine.dispose()
    logger.info("Closed database engine")


async def server_info() -> dict:
    """Return basic database information (replaces MongoDB server_info)."""
    import sqlalchemy

    url = storage._build_url()
    db_name = url.rsplit("/", 1)[-1] or "sqlite"
    return {
        "version": sqlalchemy.__version__,
        "database": db_name,
    }
