import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from bot import database
from bot.database import (
    add_reminder,
    delete_reminder,
    get_overdue_reminders,
    get_pending_reminders,
    get_reminder,
    get_saved_utc_offset,
    get_user_reminders,
    get_utc_offset,
    set_utc_offset,
    update_reminder,
)


def _in_hours(hours: float) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


@pytest.mark.asyncio
async def test_reminder_workflow():
    test_time = _in_hours(1)
    test_message = "Test reminder"

    # Тест добавления напоминания
    reminder_id = await add_reminder(123, 456, test_time, test_message)
    assert isinstance(reminder_id, int)

    # Тест получения напоминаний
    reminders = await get_pending_reminders()
    assert len(reminders) == 1
    assert reminders[0].message == test_message

    # Тест удаления напоминания
    await delete_reminder(reminder_id)
    reminders = await get_pending_reminders()
    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_add_reminder_without_message_fails():
    """Пустой текст нарушает NOT NULL в таблице."""
    with pytest.raises(sqlite3.IntegrityError):
        await add_reminder(123, 456, _in_hours(1), None)


@pytest.mark.asyncio
async def test_add_reminder_rejects_naive_time():
    """Время без часового пояса не принимается: нельзя понять, по какому оно поясу."""
    with pytest.raises(ValueError):
        await add_reminder(123, 456, datetime.now() + timedelta(hours=1), "msg")


@pytest.mark.asyncio
async def test_add_reminder_stores_time_in_utc():
    local = timezone(timedelta(hours=5))
    moment = datetime(2030, 6, 1, 14, 30, tzinfo=local)

    reminder_id = await add_reminder(123, 456, moment, "msg")

    with sqlite3.connect(database.DB_NAME) as conn:
        stored = conn.execute(
            "SELECT reminder_time FROM reminders WHERE id = ?", (reminder_id,)
        ).fetchone()[0]
    assert stored == "2030-06-01T09:30:00+00:00"


@pytest.mark.asyncio
async def test_get_user_reminders_pagination():
    user_id = 999

    # Создаёт 15 напоминаний
    for i in range(15):
        await add_reminder(user_id, 111, _in_hours(i + 1), f"Reminder {i}")

    # Первая страница
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
    reminder_id = await add_reminder(123, 456, _in_hours(1), "Original message")

    new_time = _in_hours(5)
    new_version = await update_reminder(reminder_id, reminder_time=new_time)
    assert new_version == 2

    reminder = await get_reminder(reminder_id)
    assert reminder.reminder_time == new_time
    assert reminder.message == "Original message"


@pytest.mark.asyncio
async def test_update_reminder_message():
    test_time = _in_hours(1)
    reminder_id = await add_reminder(123, 456, test_time, "Original message")

    new_version = await update_reminder(reminder_id, message="Updated message")
    assert new_version == 2

    reminder = await get_reminder(reminder_id)
    assert reminder.message == "Updated message"
    assert reminder.reminder_time == test_time


@pytest.mark.asyncio
async def test_update_reminder_both():
    reminder_id = await add_reminder(123, 456, _in_hours(1), "Original message")

    new_time = _in_hours(3)
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
    reminder_id = await add_reminder(123, 456, _in_hours(1), "Original message")

    assert await update_reminder(reminder_id, message="First") == 2
    assert await update_reminder(reminder_id, message="Second") == 3

    reminder = await get_reminder(reminder_id)
    assert reminder.version == 3


@pytest.mark.asyncio
async def test_update_reminder_not_found():
    result = await update_reminder(99999, message="test")
    assert result is None


@pytest.mark.asyncio
async def test_update_reminder_rejects_naive_time():
    reminder_id = await add_reminder(123, 456, _in_hours(1), "msg")

    with pytest.raises(ValueError):
        await update_reminder(reminder_id, reminder_time=datetime.now())


@pytest.mark.asyncio
async def test_get_overdue_reminders_returns_only_past_in_order():
    now = datetime.now(UTC)
    await add_reminder(1, 10, now - timedelta(hours=1), "newer")
    await add_reminder(1, 10, now - timedelta(hours=3), "older")
    await add_reminder(1, 10, now + timedelta(hours=1), "future")

    overdue = await get_overdue_reminders()

    assert [r.message for r in overdue] == ["older", "newer"]


@pytest.mark.asyncio
async def test_get_reminder_maps_all_fields():
    test_time = _in_hours(1)
    reminder_id = await add_reminder(123, 456, test_time, "Mapping")

    reminder = await get_reminder(reminder_id)

    assert reminder.id == reminder_id
    assert reminder.user_id == 123
    assert reminder.channel_id == 456
    assert reminder.reminder_time == test_time
    assert reminder.reminder_time.utcoffset() == timedelta(0)
    assert reminder.message == "Mapping"
    assert isinstance(reminder.created_at, datetime)
    assert reminder.created_at.tzinfo is not None
    assert reminder.version == 1


@pytest.mark.asyncio
async def test_delete_reminder():
    reminder_id = await add_reminder(123, 456, _in_hours(1), "To delete")
    reminder = await get_reminder(reminder_id)
    assert reminder is not None
    await delete_reminder(reminder_id)
    reminder = await get_reminder(reminder_id)
    assert reminder is None


# часовой пояс пользователя


@pytest.mark.asyncio
async def test_utc_offset_is_unset_by_default():
    assert await get_saved_utc_offset(1) is None
    assert await get_utc_offset(1) == 3


@pytest.mark.asyncio
async def test_set_utc_offset_is_saved_per_user():
    await set_utc_offset(1, 5)
    await set_utc_offset(2, -7)

    assert await get_saved_utc_offset(1) == 5
    assert await get_utc_offset(2) == -7
    assert await get_saved_utc_offset(3) is None


@pytest.mark.asyncio
async def test_set_utc_offset_overwrites_previous_value():
    await set_utc_offset(1, 5)
    await set_utc_offset(1, 7)

    assert await get_utc_offset(1) == 7


@pytest.mark.asyncio
async def test_zero_offset_is_not_confused_with_unset():
    await set_utc_offset(1, 0)

    assert await get_saved_utc_offset(1) == 0
    assert await get_utc_offset(1) == 0


# схема и миграции


def _create_legacy_db(path):
    """База старого формата: время хранится без пояса, по Москве."""
    with sqlite3.connect(path) as conn:
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


@pytest.mark.asyncio
async def test_init_db_adds_version_column_to_old_table(tmp_path, monkeypatch):
    """Таблица старого формата (без version) обновляется, данные сохраняются."""
    old_db = tmp_path / "old.db"
    _create_legacy_db(old_db)
    monkeypatch.setattr(database, "DB_NAME", old_db)

    await database.init_db()

    reminder = await get_reminder(1)
    assert reminder.message == "старое"
    assert reminder.version == 1


@pytest.mark.asyncio
async def test_init_db_converts_legacy_moscow_times_to_utc(tmp_path, monkeypatch):
    old_db = tmp_path / "old.db"
    _create_legacy_db(old_db)
    monkeypatch.setattr(database, "DB_NAME", old_db)

    await database.init_db()

    reminder = await get_reminder(1)
    assert reminder.reminder_time == datetime(2030, 1, 1, 7, 0, tzinfo=UTC)
    assert reminder.created_at == datetime(2029, 1, 1, 7, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_init_db_migration_runs_only_once(tmp_path, monkeypatch):
    """Повторный запуск не должен сдвигать время ещё раз."""
    old_db = tmp_path / "old.db"
    _create_legacy_db(old_db)
    monkeypatch.setattr(database, "DB_NAME", old_db)

    await database.init_db()
    await database.init_db()
    await database.init_db()

    reminder = await get_reminder(1)
    assert reminder.reminder_time == datetime(2030, 1, 1, 7, 0, tzinfo=UTC)


def _schema_version(path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


@pytest.mark.asyncio
async def test_init_db_sets_schema_version(tmp_path, monkeypatch):
    old_db = tmp_path / "old.db"
    _create_legacy_db(old_db)
    monkeypatch.setattr(database, "DB_NAME", old_db)
    assert _schema_version(old_db) == 0

    await database.init_db()

    assert _schema_version(old_db) == database.SCHEMA_VERSION


@pytest.mark.asyncio
async def test_init_db_sets_schema_version_on_new_db():
    await database.init_db()

    assert _schema_version(database.DB_NAME) == database.SCHEMA_VERSION


@pytest.mark.asyncio
async def test_init_db_skips_migration_for_current_schema(tmp_path, monkeypatch):
    """База текущей версии не пересчитывается: время в ней уже в UTC."""
    current_db = tmp_path / "current.db"
    _create_legacy_db(current_db)
    with sqlite3.connect(current_db) as conn:
        conn.execute(f"PRAGMA user_version = {database.SCHEMA_VERSION}")
    monkeypatch.setattr(database, "DB_NAME", current_db)

    await database.init_db()

    with sqlite3.connect(current_db) as conn:
        stored = conn.execute("SELECT reminder_time FROM reminders").fetchone()[0]
    assert stored == "2030-01-01T10:00:00"


@pytest.mark.asyncio
async def test_init_db_does_not_touch_new_reminders_on_restart():
    moment = datetime(2030, 6, 1, 9, 30, tzinfo=UTC)
    reminder_id = await add_reminder(1, 2, moment, "новое")

    await database.init_db()

    assert (await get_reminder(reminder_id)).reminder_time == moment


@pytest.mark.asyncio
async def test_init_db_is_idempotent():
    await database.init_db()
    await database.init_db()
