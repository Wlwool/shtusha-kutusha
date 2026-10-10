"""Часовые пояса пользователей: смещение от UTC в целых часах."""

import datetime
import re

DEFAULT_UTC_OFFSET = 3  # Москва
MIN_UTC_OFFSET = -12
MAX_UTC_OFFSET = 14

_OFFSET_PATTERN = re.compile(r"[+-]?[0-9]{1,2}")


def parse_utc_offset(text: str) -> int | None:
    """Разбор смещения от UTC вида "+5", "5" или "-3".
    Возвращает None, если это не целое число от -12 до +14.
    """
    text = text.strip()
    if not _OFFSET_PATTERN.fullmatch(text):
        return None
    hours = int(text)
    if not MIN_UTC_OFFSET <= hours <= MAX_UTC_OFFSET:
        return None
    return hours


def offset_to_tz(hours: int) -> datetime.timezone:
    return datetime.timezone(datetime.timedelta(hours=hours))


def format_utc_offset(hours: int) -> str:
    return f"UTC{hours:+d}"


def format_local(moment: datetime.datetime, hours: int) -> str:
    """Показ момента времени по часам пользователя: 25-12-2026 17:00."""
    return moment.astimezone(offset_to_tz(hours)).strftime("%d-%m-%Y %H:%M")
