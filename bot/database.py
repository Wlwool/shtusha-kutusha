import datetime
import os
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from bot.tz import DEFAULT_UTC_OFFSET

DB_DIR = Path(os.getenv("DB_DIR", Path(__file__).parent))
DB_NAME = DB_DIR / "bot.db"

# Версия схемы базы (PRAGMA user_version):
# 0 - время хранилось без пояса, по Москве. 1 - время хранится в UTC.
SCHEMA_VERSION = 1
LEGACY_UTC_OFFSET = 3


@dataclass(frozen=True, slots=True)
class Reminder:
    """Напоминание из базы данных. Время хранится и отдаётся в UTC."""
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


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def _to_utc_iso(moment: datetime.datetime) -> str:
    """Время с поясом в UTC для хранения. Время без пояса не принимается."""
    if moment.tzinfo is None:
        raise ValueError("Время напоминания должно содержать часовой пояс")
    return moment.astimezone(datetime.UTC).isoformat()


def _legacy_to_utc_iso(text: str) -> str:
    """Перевоод времени старого формата (без пояса, по Москве) в UTC."""
    moment = datetime.datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=LEGACY_UTC_OFFSET))
        )
    return moment.astimezone(datetime.UTC).isoformat()


async def _migrate(db: aiosqlite.Connection) -> None:
    """Приведение базы к текущей версии схемы. Вызывается внутри init_db."""
    cursor = await db.execute('PRAGMA user_version')
    (version,) = await cursor.fetchone()
    if version < 1:
        cursor = await db.execute('SELECT id, reminder_time, created_at FROM reminders')
        for id_, reminder_time, created_at in await cursor.fetchall():
            await db.execute(
                'UPDATE reminders SET reminder_time = ?, created_at = ? WHERE id = ?',
                (_legacy_to_utc_iso(reminder_time), _legacy_to_utc_iso(created_at), id_))
        await db.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')


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
        await db.execute('''CREATE TABLE IF NOT EXISTS user_settings
                          (user_id INTEGER PRIMARY KEY,
                           utc_offset INTEGER NOT NULL)''')
        cursor = await db.execute('PRAGMA table_info(reminders)')
        columns = {row[1] for row in await cursor.fetchall()}
        if 'version' not in columns:
            await db.execute(
                'ALTER TABLE reminders ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
        await _migrate(db)
        await db.commit()


async def get_saved_utc_offset(user_id: int) -> int | None:
    """Смещение от UTC, выбранное пользователем, или None, если он его не выбирал."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT utc_offset FROM user_settings WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_utc_offset(user_id: int) -> int:
    """Смещение от UTC пользователя: выбранное или по умолчанию (Москва)."""
    saved = await get_saved_utc_offset(user_id)
    return DEFAULT_UTC_OFFSET if saved is None else saved


async def set_utc_offset(user_id: int, hours: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            '''INSERT INTO user_settings (user_id, utc_offset) VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET utc_offset = excluded.utc_offset''',
            (user_id, hours))
        await db.commit()


async def add_reminder(
    user_id: int, channel_id: int, reminder_time: datetime.datetime, message: str
) -> int:
    time_iso = _to_utc_iso(reminder_time)
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''INSERT INTO reminders 
                                  (user_id, channel_id, reminder_time, message, created_at)
                                  VALUES (?, ?, ?, ?, ?)''',
                                  (user_id, channel_id, time_iso, message, _now_iso()))
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
            (_now_iso(),))
        return [Reminder.from_row(row) for row in await cursor.fetchall()]


async def get_overdue_reminders() -> list[Reminder]:
    """Напоминания, время которых уже наступило, но которые ещё не отправлены."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            '''SELECT id, user_id, channel_id, reminder_time, message, created_at, version
               FROM reminders
               WHERE reminder_time <= ?
               ORDER BY reminder_time ASC''',
            (_now_iso(),))
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
            (user_id, _now_iso()))
        total = (await cursor.fetchone())[0]

        # Записи с пагинацией
        cursor = await db.execute(
            '''SELECT id, user_id, channel_id, reminder_time, message, created_at, version
               FROM reminders
               WHERE user_id = ? AND reminder_time > ?
               ORDER BY reminder_time ASC
               LIMIT ? OFFSET ?''',
            (user_id, _now_iso(), limit, offset)
        )
        return [Reminder.from_row(row) for row in await cursor.fetchall()], total


async def update_reminder(
    reminder_id: int,
    reminder_time: datetime.datetime | None = None,
    message: str | None = None,
) -> int | None:
    """
    Возвращает новый version или None если не найдено.
    """
    time_iso = None if reminder_time is None else _to_utc_iso(reminder_time)
    async with aiosqlite.connect(DB_NAME) as db:
        if time_iso is not None and message is not None:
            await db.execute(
                'UPDATE reminders SET reminder_time = ?, message = ?, version = version + 1 WHERE id = ?',
                (time_iso, message, reminder_id)
            )
        elif time_iso is not None:
            await db.execute(
                'UPDATE reminders SET reminder_time = ?, version = version + 1 WHERE id = ?',
                (time_iso, reminder_id)
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
