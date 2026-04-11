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
                           created_at TEXT NOT NULL)''')
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
        cursor = await db.execute('SELECT COUNT(*) FROM reminders WHERE user_id = ?', (user_id,))
        total = (await cursor.fetchone())[0]

        # Записи с пагинацией
        cursor = await db.execute(
            '''SELECT id, reminder_time, message, channel_id, created_at
               FROM reminders
               WHERE user_id = ?
               ORDER BY reminder_time ASC
               LIMIT ? OFFSET ?''',
            (user_id, limit, offset)
        )
        return await cursor.fetchall(), total


async def update_reminder(
    reminder_id: int,
    reminder_time: Optional[datetime.datetime] = None,
    message: Optional[str] = None,
) -> bool:
    """Обновить время или текст напоминания. Возвращает True если запись найдена"""
    async with aiosqlite.connect(DB_NAME) as db:
        if reminder_time is not None and message is not None:
            await db.execute(
                'UPDATE reminders SET reminder_time = ?, message = ? WHERE id = ?',
                (reminder_time.isoformat(), message, reminder_id)
            )
        elif reminder_time is not None:
            await db.execute(
                'UPDATE reminders SET reminder_time = ? WHERE id = ?',
                (reminder_time.isoformat(), reminder_id)
            )
        elif message is not None:
            await db.execute(
                'UPDATE reminders SET message = ? WHERE id = ?',
                (message, reminder_id)
            )
        else:
            return False
        await db.commit()
        return db.total_changes > 0


async def get_reminder(reminder_id: int) -> Tuple:
    """Получить напоминание по ID"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT * FROM reminders WHERE id = ?', (reminder_id,))
        return await cursor.fetchone()
