"""Тесты StatusCog: запуск статуса и повторный on_ready."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.cogs.status import StatusCog


@pytest.fixture
async def cog():
    scheduler = AsyncIOScheduler()
    scheduler.start()
    bot = SimpleNamespace(
        user=SimpleNamespace(id=1),
        guilds=[],
        latency=0.05,
        change_presence=AsyncMock(),
        scheduler=scheduler,
        send_reminder=AsyncMock(),
    )
    cog = StatusCog(bot)
    yield cog
    cog._update_status.cancel()
    scheduler.shutdown(wait=False)


async def test_on_ready_starts_status_loop(cog):
    await cog.on_ready()

    assert cog._update_status.is_running()


async def test_on_ready_twice_does_not_raise(cog):
    """Discord может вызвать on_ready повторно (например, после переподключения)"""
    await cog.on_ready()

    await cog.on_ready()

    assert cog._update_status.is_running()


async def test_on_ready_twice_keeps_single_status_loop(cog):
    await cog.on_ready()
    task = cog._update_status.get_task()

    await cog.on_ready()

    assert cog._update_status.get_task() is task
