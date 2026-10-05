import pytest

import main


@pytest.mark.asyncio
async def test_lifespan_initializes_recovers_and_closes_pool(monkeypatch):
    calls = []

    async def init_db():
        calls.append("init")

    async def recover():
        calls.append("recover")

    async def close_db():
        calls.append("close")

    monkeypatch.setattr(main, "init_db", init_db)
    monkeypatch.setattr(main, "recover_orphaned_jobs", recover)
    monkeypatch.setattr(main, "close_db", close_db)

    async with main.lifespan(main.app):
        calls.append("serve")

    assert calls == ["init", "recover", "serve", "close"]


@pytest.mark.asyncio
async def test_lifespan_closes_pool_when_startup_recovery_fails(monkeypatch):
    calls = []

    async def init_db():
        calls.append("init")

    async def recover():
        calls.append("recover")
        raise RuntimeError("recovery failed")

    async def close_db():
        calls.append("close")

    monkeypatch.setattr(main, "init_db", init_db)
    monkeypatch.setattr(main, "recover_orphaned_jobs", recover)
    monkeypatch.setattr(main, "close_db", close_db)

    with pytest.raises(RuntimeError, match="recovery failed"):
        async with main.lifespan(main.app):
            pytest.fail("Application must not start if recovery fails.")

    assert calls == ["init", "recover", "close"]
