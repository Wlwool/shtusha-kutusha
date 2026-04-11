"""Тесты редактирования напоминаний через EditReminderModal."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from bot.database import add_reminder, get_reminder, update_reminder


@pytest.fixture(autouse=True)
async def setup_db():
    import aiosqlite
    from bot.database import DB_NAME, init_db

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM reminders")
        await db.commit()
    await init_db()
    yield
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM reminders")
        await db.commit()


@pytest.mark.asyncio
async def test_update_reminder_updates_db():
    """Проверка что update_reminder меняет данные в БД."""
    test_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    rid = await add_reminder(123, 456, test_time, "Old message")

    new_time = datetime.datetime.now() + datetime.timedelta(hours=3)
    result = await update_reminder(rid, reminder_time=new_time, message="New message")
    assert result is True

    reminder = await get_reminder(rid)
    assert datetime.datetime.fromisoformat(reminder[3]) == new_time
    assert reminder[4] == "New message"


@pytest.mark.asyncio
async def test_scheduler_modify_job_exists():
    """modify_job вызывается когда job есть в scheduler."""
    scheduler = AsyncIOScheduler()
    scheduler.start()
    send_mock = AsyncMock()
    run_date = datetime.datetime.now() + datetime.timedelta(hours=1)
    scheduler.add_job(
        send_mock, "date", run_date=run_date,
        args=(1, 2, "msg", 1), id="1",)
    new_time = datetime.datetime.now() + datetime.timedelta(hours=2)
    scheduler.modify_job("1", trigger=DateTrigger(run_date=new_time), args=(1, 2, "new_msg", 1))
    job = scheduler.get_job("1")
    assert job is not None
    assert job.args == (1, 2, "new_msg", 1)
    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_modify_job_not_found():
    """LookupError при modify_job для несуществующего job."""
    scheduler = AsyncIOScheduler()

    with pytest.raises(LookupError):
        scheduler.modify_job("nonexistent", trigger="date", run_date=datetime.datetime.now())


@pytest.mark.asyncio
async def test_scheduler_add_job_after_remove():
    scheduler = AsyncIOScheduler()
    scheduler.start()
    send_mock = AsyncMock()
    run_date = datetime.datetime.now() + datetime.timedelta(minutes=1)
    scheduler.add_job(send_mock, "date", run_date=run_date, args=(1,), id="1")
    scheduler.remove_job("1")
    assert scheduler.get_job("1") is None
    new_time = datetime.datetime.now() + datetime.timedelta(minutes=5)
    scheduler.add_job(send_mock, "date", run_date=new_time, args=(2,), id="1")
    job = scheduler.get_job("1")
    assert job is not None
    assert job.args == (2,)

    scheduler.shutdown(wait=False)
