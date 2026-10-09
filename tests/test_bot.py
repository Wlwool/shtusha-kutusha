import sqlite3
from datetime import datetime, timedelta

import pytest

from bot import database
from bot.database import (
    add_reminder,
    delete_reminder,
    get_pending_reminders,
    get_reminder,
    get_user_reminders,
    update_reminder,
)
from bot.utils import parse_time


@pytest.mark.asyncio
async def test_reminder_workflow():
    test_time = datetime.now() + timedelta(hours=1)
    test_message = "Test reminder"

    reminder_id = await add_reminder(123, 456, test_time, test_message)
    assert isinstance(reminder_id, int)

    reminders = await get_pending_reminders()
    assert len(reminders) == 1
    assert reminders[0].message == test_message

    await delete_reminder(reminder_id)
    reminders = await get_pending_reminders()
    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_add_reminder_without_message_fails():
    """Пустой текст нарушает NOT NULL в таблице."""
    test_time = datetime.now() + timedelta(hours=1)
    with pytest.raises(sqlite3.IntegrityError):
        await add_reminder(123, 456, test_time, None)


@pytest.mark.asyncio
async def test_get_user_reminders_pagination():
    user_id = 999
    now = datetime.now()

    for i in range(15):
        await add_reminder(user_id, 111, now + timedelta(hours=i + 1), f"Reminder {i}")

    reminders, total = await get_user_reminders(user_id, limit=10, offset=0)
    assert total == 15
    assert len(reminders) == 10
    assert reminders[0].message == "Reminder 0"
    assert reminders[0].user_id == user_id
    assert reminders[0].channel_id == 111

    # Вторая страница
    reminders, total = await get_user_reminders(user_id, limit=10, offset=10)
    assert len(reminders) == 5
    assert reminders[0].message == "Reminder 10"


@pytest.mark.asyncio
async def test_get_user_reminders_empty():
    reminders, total = await get_user_reminders(0, limit=10, offset=0)
    assert total == 0
    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_update_reminder_time():
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "Original message")

    new_time = datetime.now() + timedelta(hours=5)
    new_version = await update_reminder(reminder_id, reminder_time=new_time)
    assert new_version == 2

    reminder = await get_reminder(reminder_id)
    assert reminder.reminder_time == new_time
    assert reminder.message == "Original message"


@pytest.mark.asyncio
async def test_update_reminder_message():
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "Original message")

    new_version = await update_reminder(reminder_id, message="Updated message")
    assert new_version == 2

    reminder = await get_reminder(reminder_id)
    assert reminder.message == "Updated message"
    assert reminder.reminder_time == test_time


@pytest.mark.asyncio
async def test_update_reminder_both():
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "Original message")

    new_time = datetime.now() + timedelta(hours=3)
    new_version = await update_reminder(
        reminder_id, reminder_time=new_time, message="New message"
    )
    assert new_version == 2

    reminder = await get_reminder(reminder_id)
    assert reminder.reminder_time == new_time
    assert reminder.message == "New message"


@pytest.mark.asyncio
async def test_update_reminder_increments_version():
    """Каждое изменение увеличивает version: по нему отсекаются устаревшие задачи."""
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "Original message")

    assert await update_reminder(reminder_id, message="First") == 2
    assert await update_reminder(reminder_id, message="Second") == 3

    reminder = await get_reminder(reminder_id)
    assert reminder.version == 3


@pytest.mark.asyncio
async def test_update_reminder_not_found():
    result = await update_reminder(99999, message="test")
    assert result is None


@pytest.mark.asyncio
async def test_get_reminder_maps_all_fields():
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "Mapping")

    reminder = await get_reminder(reminder_id)

    assert reminder.id == reminder_id
    assert reminder.user_id == 123
    assert reminder.channel_id == 456
    assert reminder.reminder_time == test_time
    assert reminder.message == "Mapping"
    assert isinstance(reminder.created_at, datetime)
    assert reminder.version == 1


@pytest.mark.asyncio
async def test_get_overdue_reminders_returns_only_past_in_order():
    now = datetime.now()
    await add_reminder(1, 10, now - timedelta(hours=1), "newer")
    await add_reminder(1, 10, now - timedelta(hours=3), "older")
    await add_reminder(1, 10, now + timedelta(hours=1), "future")

    overdue = await database.get_overdue_reminders()

    assert [r.message for r in overdue] == ["older", "newer"]


@pytest.mark.asyncio
async def test_init_db_adds_version_column_to_old_table(tmp_path, monkeypatch):
    """Таблица старого формата (без version) обновляется, данные сохраняются."""
    old_db = tmp_path / "old.db"
    with sqlite3.connect(old_db) as conn:
        conn.execute(
            """CREATE TABLE reminders (id INTEGER PRIMARY KEY AUTOINCREMENT,
               user_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
               reminder_time TEXT NOT NULL, message TEXT NOT NULL,
               created_at TEXT NOT NULL)"""
        )
        conn.execute(
            "INSERT INTO reminders (user_id, channel_id, reminder_time, message, created_at)"
            " VALUES (1, 2, '2030-01-01T10:00:00', 'старое', '2029-01-01T10:00:00')"
        )
    monkeypatch.setattr(database, "DB_NAME", old_db)

    await database.init_db()

    reminder = await get_reminder(1)
    assert reminder.message == "старое"
    assert reminder.version == 1


@pytest.mark.asyncio
async def test_init_db_is_idempotent():
    await database.init_db()
    await database.init_db()


@pytest.mark.asyncio
async def test_delete_reminder():
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "To delete")
    reminder = await get_reminder(reminder_id)
    assert reminder is not None
    await delete_reminder(reminder_id)
    reminder = await get_reminder(reminder_id)
    assert reminder is None


def test_parse_time_dd_mm_yyyy_with_time():
    """Формат dd.mm.yyyy HH:MM 25.12.2026 14:30"""
    result = parse_time("25.12.2026 14:30")
    assert result == datetime(2026, 12, 25, 14, 30)


def test_parse_time_dd_mm_yyyy_without_time():
    result = parse_time("11.04.2026")
    assert result == datetime(2026, 4, 11, 0, 0)


def test_parse_time_slash_separator():
    result = parse_time("11/04/2026")
    assert result == datetime(2026, 4, 11, 0, 0)


def test_parse_time_slash_with_time():
    result = parse_time("25/12/2026 09:00")
    assert result == datetime(2026, 12, 25, 9, 0)


def test_parse_time_relative():
    result = parse_time("in 2 hours")
    assert result is not None
    assert result > datetime.now()


def test_parse_time_invalid():
    """Невалидная дата - 32.13.2026"""
    result = parse_time("32.13.2026")
    assert result is None


def test_parse_time_dash_separator():
    """Формат dd-mm-yyyy - 11-04-2026"""
    result = parse_time("11-04-2026")
    assert result == datetime(2026, 4, 11, 0, 0)


def test_parse_time_dash_with_time():
    result = parse_time("25-12-2026 09:00")
    assert result == datetime(2026, 12, 25, 9, 0)


def test_parse_time_dash_ambiguous_day_gt_12():
    result = parse_time("25-04-2026")
    assert result == datetime(2026, 4, 25, 0, 0)
