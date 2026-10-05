"""
database.py — asyncpg connection pool initialisation and teardown.
Owner: Person 3 (M.9)

TODO (Person 3 — M.9):
  - Call init_db() in the FastAPI lifespan startup.
  - Call close_db() in the FastAPI lifespan shutdown.
  - Use get_pool() in repositories to obtain a connection.
"""
import asyncpg
from pathlib import Path

from app.config import settings

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Create the asyncpg connection pool."""
    global _pool
    # TODO (Person 3 — M.9): Tune min_size / max_size for production load.
    _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)


async def close_db() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def run_migrations() -> None:
    """Apply the idempotent initial schema on startup."""
    pool = get_pool()
    migration = Path(__file__).parent / "persistence" / "migrations" / "001_initial.sql"
    async with pool.acquire() as conn:
        await conn.execute(migration.read_text())


def get_pool() -> asyncpg.Pool:
    """Return the active pool. Raises RuntimeError if not initialised."""
    if _pool is None:
        raise RuntimeError("Database pool is not initialised. Call init_db() first.")
    return _pool
