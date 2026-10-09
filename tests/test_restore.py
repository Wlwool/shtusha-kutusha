"""Тесты восстановления напоминаний при старте (StatusCog._restore_reminders)."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.cogs.status import StatusCog
from bot.database import add_reminder


@pytest.fixture
async def fake_bot():
    scheduler = AsyncIOScheduler()
    scheduler.start()
    yield SimpleNamespace(scheduler=scheduler, send_reminder=AsyncMock())
    scheduler.shutdown(wait=False)


async def test_restore_sends_overdue_and_schedules_future(fake_bot):
    now = datetime.datetime.now()
    overdue_id = await add_reminder(1, 10, now - datetime.timedelta(hours=2), "просрочено")
    future_id = await add_reminder(2, 20, now + datetime.timedelta(hours=2), "будущее")

    await StatusCog(fake_bot)._restore_reminders()

    fake_bot.send_reminder.assert_awaited_once_with(1, 10, "просрочено", overdue_id, 1)
    assert fake_bot.scheduler.get_job(str(future_id)) is not None
    assert fake_bot.scheduler.get_job(str(overdue_id)) is None
