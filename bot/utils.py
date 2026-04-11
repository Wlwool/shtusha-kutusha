from __future__ import annotations

import datetime
import os
import re
from typing import Optional
from dateparser import parse
from discord.ext import commands

# парсинг времени и проверка прав администратора
def parse_time(time_str: str) -> Optional[datetime.datetime]:
    """Парсит время из строки.

    Поддерживаемые форматы:
        - dd.mm.yyyy HH:MM / dd/mm/yyyy HH:MM / dd-mm-yyyy HH:MM
        - dd.mm.yyyy / dd/mm/yyyy / dd-mm-yyyy
        - Относительные: "in 2 hours", "через 30 минут" (через dateparser)

    Args:
        time_str: Строка с временем.

    Returns:
        datetime.datetime или None, если распарсить не удалось.
    """
    m = re.match(r"(\d{2})[./-](\d{2})[./-](\d{4})\s+(\d{2}):(\d{2})", time_str)
    if m:
        day, month, year, hour, minute = m.groups()
        try:
            return datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
        except ValueError:
            return None

    m = re.match(r"(\d{2})[./-](\d{2})[./-](\d{4})\s*$", time_str)
    if m:
        day, month, year = m.groups()
        try:
            return datetime.datetime(int(year), int(month), int(day), 0, 0)
        except ValueError:
            return None

    return parse(time_str, settings={"RELATIVE_BASE": datetime.datetime.now()})


def is_admin() -> commands.CheckPredicate:
    """Проверка прав администратора через ADMIN_ID из окружения."""
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id:
        raise commands.CheckFailure("ADMIN_ID не установлен в .env")

    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id == int(admin_id)

    return commands.check(predicate)
