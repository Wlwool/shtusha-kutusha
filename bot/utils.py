from __future__ import annotations

import datetime
import os
import re

from dateparser import parse
from discord.ext import commands

from bot.tz import DEFAULT_UTC_OFFSET, offset_to_tz


# парсинг времени и проверка прав администратора
def parse_time(
    time_str: str, utc_offset: int = DEFAULT_UTC_OFFSET
) -> datetime.datetime | None:
    """Парсит время из строки по часам пользователя.
    Поддерживаемые форматы:
        - dd.mm.yyyy HH:MM / dd/mm/yyyy HH:MM / dd-mm-yyyy HH:MM
        - dd.mm.yyyy / dd/mm/yyyy / dd-mm-yyyy
        - Относительные: "in 2 hours", "через 30 минут" (через dateparser)

    Args:
        time_str: Строка с временем.
        utc_offset: Смещение пользователя от UTC в часах.

    Returns:
        datetime.datetime с часовым поясом пользователя или None, если
        распарсить не удалось.
    """
    tz = offset_to_tz(utc_offset)

    m = re.match(r"(\d{2})[./-](\d{2})[./-](\d{4})\s+(\d{2}):(\d{2})", time_str)
    if m:
        day, month, year, hour, minute = m.groups()
        try:
            return datetime.datetime(
                int(year), int(month), int(day), int(hour), int(minute), tzinfo=tz
            )
        except ValueError:
            return None

    m = re.match(r"(\d{2})[./-](\d{2})[./-](\d{4})\s*$", time_str)
    if m:
        day, month, year = m.groups()
        try:
            return datetime.datetime(int(year), int(month), int(day), 0, 0, tzinfo=tz)
        except ValueError:
            return None

    # Относительное время считается от часов пользователя, а не сервера.
    now_local = datetime.datetime.now(tz).replace(tzinfo=None)
    parsed = parse(time_str, settings={"RELATIVE_BASE": now_local})
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=tz)


def is_admin() -> commands.CheckPredicate:
    """Проверка прав администратора через ADMIN_ID из окружения."""
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id:
        raise commands.CheckFailure("ADMIN_ID не установлен в .env")

    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id == int(admin_id)

    return commands.check(predicate)
