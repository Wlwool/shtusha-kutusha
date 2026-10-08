"""Тесты вспомогательных функций планировщика из bot.ui.reminder_view."""
from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.ui.reminder_view import _scheduler_add, _scheduler_remove


@pytest.fixture
async def fake_bot():
    """Минимальная замена бота: настоящий планировщик и мок send_reminder."""
    scheduler = AsyncIOScheduler()
    scheduler.start()
    yield SimpleNamespace(scheduler=scheduler, send_reminder=AsyncMock())
    scheduler.shutdown(wait=False)


def _in_hours(hours: int) -> datetime.datetime:
    return datetime.datetime.now() + datetime.timedelta(hours=hours)


async def test_scheduler_add_creates_job(fake_bot):
    run_date = _in_hours(1)
    args = (1, 2, "msg", 7, 1)

    _scheduler_add(fake_bot, 7, run_date, args)

    job = fake_bot.scheduler.get_job("7")
    assert job is not None
    assert job.args == args
    assert job.func is fake_bot.send_reminder
    # next_run_time содержит часовой пояс, run_date нет: сравниваем без пояса
    next_naive = job.next_run_time.replace(tzinfo=None)
    assert abs((next_naive - run_date).total_seconds()) < 2


async def test_scheduler_add_replaces_job_with_same_id(fake_bot):
    _scheduler_add(fake_bot, 7, _in_hours(1), (1, 2, "old", 7, 1))
    _scheduler_add(fake_bot, 7, _in_hours(2), (1, 2, "new", 7, 2))

    jobs = fake_bot.scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].args == (1, 2, "new", 7, 2)


async def test_scheduler_remove_deletes_job(fake_bot):
    _scheduler_add(fake_bot, 7, _in_hours(1), (1, 2, "msg", 7, 1))

    _scheduler_remove(fake_bot, 7)

    assert fake_bot.scheduler.get_job("7") is None


async def test_scheduler_remove_missing_job_does_not_raise(fake_bot):
    _scheduler_remove(fake_bot, 12345)

    assert fake_bot.scheduler.get_jobs() == []
