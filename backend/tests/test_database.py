import pytest

from app import database


class FakePool:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


def test_get_pool_requires_initialisation(monkeypatch):
    monkeypatch.setattr(database, "_pool", None)

    with pytest.raises(RuntimeError, match="not initialised"):
        database.get_pool()


@pytest.mark.asyncio
async def test_init_and_close_db_manage_the_shared_pool(monkeypatch):
    created_pool = FakePool()

    async def create_pool(database_url, *, min_size, max_size):
        assert database_url.endswith("resume_screening_test")
        assert (min_size, max_size) == (2, 10)
        return created_pool

    monkeypatch.setattr(database, "_pool", None)
    monkeypatch.setattr(database.asyncpg, "create_pool", create_pool)

    await database.init_db()
    assert database.get_pool() is created_pool

    await database.close_db()
    assert created_pool.closed is True
    with pytest.raises(RuntimeError, match="not initialised"):
        database.get_pool()
