"""Тесты редактирования и удаления напоминаний через scheduler."""
from __future__ import annotations
import datetime
from unittest.mock import AsyncMock
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
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
async def test_scheduler_reschedule_job_changes_time():
    """reschedule_job корректно меняет время срабатывания."""
    scheduler = AsyncIOScheduler()
    scheduler.start()

    send_mock = AsyncMock()
    old_time = datetime.datetime.now() + datetime.timedelta(hours=5)
    scheduler.add_job(
        send_mock, "date", run_date=old_time,
        args=(1, 2, "msg", 1), id="1",
    )

    # Перенос на другое время
    new_time = datetime.datetime.now() + datetime.timedelta(minutes=1)
    scheduler.reschedule_job("1", trigger="date", run_date=new_time)

    job = scheduler.get_job("1")
    assert job is not None
    assert job.next_run_time is not None
    # next_run_time может быть timezone-aware, приводим к naive для сравнения
    next_naive = job.next_run_time.replace(tzinfo=None)
    assert abs((next_naive - new_time).total_seconds()) < 2

    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_modify_job_changes_args():
    """modify_job корректно меняет аргументы задачи."""
    scheduler = AsyncIOScheduler()
    scheduler.start()

    send_mock = AsyncMock()
    run_date = datetime.datetime.now() + datetime.timedelta(hours=1)
    scheduler.add_job(
        send_mock, "date", run_date=run_date,
        args=(1, 2, "old_msg", 1), id="1",
    )

    scheduler.modify_job("1", args=(1, 2, "new_msg", 1))

    job = scheduler.get_job("1")
    assert job is not None
    assert job.args == (1, 2, "new_msg", 1)

    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_remove_job():
    """remove_job удаляет задачу из scheduler."""
    scheduler = AsyncIOScheduler()
    scheduler.start()

    send_mock = AsyncMock()
    run_date = datetime.datetime.now() + datetime.timedelta(hours=1)
    scheduler.add_job(send_mock, "date", run_date=run_date, args=(1,), id="1")

    assert scheduler.get_job("1") is not None
    scheduler.remove_job("1")
    assert scheduler.get_job("1") is None

    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_remove_nonexistent_job():
    """remove_job на несуществующей задаче бросает JobLookupError."""
    scheduler = AsyncIOScheduler()

    with pytest.raises(JobLookupError):
        scheduler.remove_job("nonexistent")


@pytest.mark.asyncio
async def test_scheduler_reschedule_nonexistent_job():
    """reschedule_job на несуществующей задаче бросает JobLookupError."""
    scheduler = AsyncIOScheduler()

    with pytest.raises(JobLookupError):
        scheduler.reschedule_job("nonexistent", trigger="date", run_date=datetime.datetime.now())
