"""asyncpg connection pool initialisation and teardown (M.9)."""
import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Create the asyncpg connection pool."""
    global _pool
    _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)


async def close_db() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the active pool. Raises RuntimeError if not initialised."""
    if _pool is None:
        raise RuntimeError("Database pool is not initialised. Call init_db() first.")
    return _pool
