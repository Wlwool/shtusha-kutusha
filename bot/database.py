import os
import aiosqlite
import datetime
from pathlib import Path
from typing import List, Tuple, Optional

DB_DIR = Path(os.getenv("DB_DIR", Path(__file__).parent))
DB_NAME = DB_DIR / "bot.db"


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

async def get_pending_reminders() -> List[Tuple]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''SELECT * FROM reminders
                                  WHERE reminder_time > ?''',
                                  (datetime.datetime.now().isoformat(),))
        return await cursor.fetchall()


async def get_user_reminders(user_id: int, limit: int = 10, offset: int = 0) -> Tuple[List[Tuple], int]:
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
            '''SELECT id, reminder_time, message, channel_id, created_at
               FROM reminders
               WHERE user_id = ? AND reminder_time > ?
               ORDER BY reminder_time ASC
               LIMIT ? OFFSET ?''',
            (user_id, datetime.datetime.now().isoformat(), limit, offset)
        )
        return await cursor.fetchall(), total


async def update_reminder(
    reminder_id: int,
    reminder_time: Optional[datetime.datetime] = None,
    message: Optional[str] = None,) -> int | None:
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


async def get_reminder(reminder_id: int) -> Tuple:
    """Получить напоминание по ID"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT * FROM reminders WHERE id = ?', (reminder_id,))
        return await cursor.fetchone()
