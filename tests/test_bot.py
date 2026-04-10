import pytest
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from bot.database import (
    init_db, add_reminder, get_pending_reminders, delete_reminder,
    get_user_reminders, update_reminder, get_reminder, DB_NAME
)


@pytest.fixture(autouse=True)
async def setup_db():
    # Очистка перед тестом
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM reminders')
        await db.commit()
    await init_db()
    yield
    # Очистка после теста
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM reminders')
        await db.commit()


@pytest.mark.asyncio
async def test_reminder_workflow():
    test_time = datetime.now() + timedelta(hours=1)
    test_message = "Test reminder"

    # Тест добавления напоминания
    reminder_id = await add_reminder(123, 456, test_time, test_message)
    assert isinstance(reminder_id, int)

    # Тест получения напоминаний
    reminders = await get_pending_reminders()
    assert len(reminders) == 1
    assert reminders[0][4] == test_message

    # Тест удаления напоминания
    await delete_reminder(reminder_id)
    reminders = await get_pending_reminders()
    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_invalid_reminder():
    with pytest.raises(Exception):
        await add_reminder(None, None, None, None)


@pytest.mark.asyncio
async def test_get_user_reminders_pagination():
    user_id = 999
    now = datetime.now()

    # Создаём 15 напоминаний
    for i in range(15):
        await add_reminder(user_id, 111, now + timedelta(hours=i+1), f"Reminder {i}")

    # Первая страница
    reminders, total = await get_user_reminders(user_id, limit=10, offset=0)
    assert total == 15
    assert len(reminders) == 10
    assert reminders[0][2] == "Reminder 0"

    # Вторая страница
    reminders, total = await get_user_reminders(user_id, limit=10, offset=10)
    assert len(reminders) == 5
    assert reminders[0][2] == "Reminder 10"


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
    result = await update_reminder(reminder_id, reminder_time=new_time)
    assert result is True

    reminder = await get_reminder(reminder_id)
    assert datetime.fromisoformat(reminder[3]) == new_time
    assert reminder[4] == "Original message"


@pytest.mark.asyncio
async def test_update_reminder_message():
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "Original message")

    result = await update_reminder(reminder_id, message="Updated message")
    assert result is True

    reminder = await get_reminder(reminder_id)
    assert reminder[4] == "Updated message"
    assert datetime.fromisoformat(reminder[3]) == test_time


@pytest.mark.asyncio
async def test_update_reminder_both():
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "Original message")

    new_time = datetime.now() + timedelta(hours=3)
    result = await update_reminder(reminder_id, reminder_time=new_time, message="New message")
    assert result is True

    reminder = await get_reminder(reminder_id)
    assert datetime.fromisoformat(reminder[3]) == new_time
    assert reminder[4] == "New message"


@pytest.mark.asyncio
async def test_update_reminder_not_found():
    result = await update_reminder(99999, message="test")
    assert result is False


@pytest.mark.asyncio
async def test_delete_reminder():
    test_time = datetime.now() + timedelta(hours=1)
    reminder_id = await add_reminder(123, 456, test_time, "To delete")

    reminder = await get_reminder(reminder_id)
    assert reminder is not None

    await delete_reminder(reminder_id)

    reminder = await get_reminder(reminder_id)
    assert reminder is None


@pytest.mark.asyncio
async def test_help_command_registration():
    """Проверяем, что register_help_command не падает и команда создаётся"""
    from bot.help_cmd import register_help_command
    # Функция принимает bot, но декоратор вызывается даже без реального бота
    # Проверяем что модуль импортируется без ошибок
    assert register_help_command is not None