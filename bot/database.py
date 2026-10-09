import datetime
import os
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

DB_DIR = Path(os.getenv("DB_DIR", Path(__file__).parent))
DB_NAME = DB_DIR / "bot.db"


@dataclass(frozen=True, slots=True)
class Reminder:
    """Напоминание из базы данных."""

    id: int
    user_id: int
    channel_id: int
    reminder_time: datetime.datetime
    message: str
    created_at: datetime.datetime
    version: int

    @classmethod
    def from_row(cls, row: tuple) -> "Reminder":
        """Собрать напоминание из строки таблицы reminders.

        Порядок столбцов в строке: id, user_id, channel_id, reminder_time,
        message, created_at, version.
        """
        id_, user_id, channel_id, reminder_time, message, created_at, version = row
        return cls(
            id=id_,
            user_id=user_id,
            channel_id=channel_id,
            reminder_time=datetime.datetime.fromisoformat(reminder_time),
            message=message,
            created_at=datetime.datetime.fromisoformat(created_at),
            version=version,
        )


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS reminders
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           user_id INTEGER NOT NULL,
                           channel_id INTEGER NOT NULL,
                           reminder_time TEXT NOT NULL,
                           message TEXT NOT NULL,
                           created_at TEXT NOT NULL,
                           version INTEGER NOT NULL DEFAULT 1)''')
        try:
            await db.execute('ALTER TABLE reminders ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
        except Exception:
            pass
        await db.commit()

async def add_reminder(user_id: int, channel_id: int, reminder_time: datetime.datetime, message: str) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''INSERT INTO reminders 
                                  (user_id, channel_id, reminder_time, message, created_at)
                                  VALUES (?, ?, ?, ?, ?)''',
                                  (user_id, channel_id, reminder_time.isoformat(), message,
                                   datetime.datetime.now().isoformat()))
        await db.commit()
        return cursor.lastrowid


async def delete_reminder(reminder_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
        await db.commit()

async def get_pending_reminders() -> list[Reminder]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            '''SELECT id, user_id, channel_id, reminder_time, message, created_at, version
               FROM reminders
               WHERE reminder_time > ?''',
            (datetime.datetime.now().isoformat(),))
        return [Reminder.from_row(row) for row in await cursor.fetchall()]


async def get_user_reminders(
    user_id: int, limit: int = 10, offset: int = 0
) -> tuple[list[Reminder], int]:
    """Получает напоминания пользователя с пагинацией.
    Возвращает: записи, общее_количество
    """
    async with aiosqlite.connect(DB_NAME) as db:
        # Общее количество
        cursor = await db.execute(
            'SELECT COUNT(*) FROM reminders WHERE user_id = ? AND reminder_time > ?',
            (user_id, datetime.datetime.now().isoformat()))
        total = (await cursor.fetchone())[0]

        # Записи с пагинацией
        cursor = await db.execute(
            '''SELECT id, user_id, channel_id, reminder_time, message, created_at, version
               FROM reminders
               WHERE user_id = ? AND reminder_time > ?
               ORDER BY reminder_time ASC
               LIMIT ? OFFSET ?''',
            (user_id, datetime.datetime.now().isoformat(), limit, offset)
        )
        return [Reminder.from_row(row) for row in await cursor.fetchall()], total


async def update_reminder(
    reminder_id: int,
    reminder_time: datetime.datetime | None = None,
    message: str | None = None,
) -> int | None:
    """Обновить напоминание.
    Возвращает новый version или None если не найдено.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        if reminder_time is not None and message is not None:
            await db.execute(
                'UPDATE reminders SET reminder_time = ?, message = ?, version = version + 1 WHERE id = ?',
                (reminder_time.isoformat(), message, reminder_id)
            )
        elif reminder_time is not None:
            await db.execute(
                'UPDATE reminders SET reminder_time = ?, version = version + 1 WHERE id = ?',
                (reminder_time.isoformat(), reminder_id)
            )
        elif message is not None:
            await db.execute(
                'UPDATE reminders SET message = ?, version = version + 1 WHERE id = ?',
                (message, reminder_id)
            )
        else:
            return None
        await db.commit()
        if db.total_changes == 0:
            return None
        cursor = await db.execute('SELECT version FROM reminders WHERE id = ?', (reminder_id,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_reminder(reminder_id: int) -> Reminder | None:
    """Получить напоминание по ID"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            '''SELECT id, user_id, channel_id, reminder_time, message, created_at, version
               FROM reminders WHERE id = ?''',
            (reminder_id,))
        row = await cursor.fetchone()
        return Reminder.from_row(row) if row else None
