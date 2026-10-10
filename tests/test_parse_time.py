"""Тесты разбора времени с учётом часового пояса пользователя."""
from datetime import UTC, datetime, timedelta, timezone

import pytest

from bot.utils import parse_time

MSK = timezone(timedelta(hours=3))
UTC5 = timezone(timedelta(hours=5))


def test_parse_time_dd_mm_yyyy_with_time():
    assert parse_time("25.12.2026 14:30") == datetime(2026, 12, 25, 14, 30, tzinfo=MSK)


def test_parse_time_dd_mm_yyyy_without_time():
    assert parse_time("11.04.2026") == datetime(2026, 4, 11, 0, 0, tzinfo=MSK)


def test_parse_time_slash_separator():
    assert parse_time("11/04/2026") == datetime(2026, 4, 11, 0, 0, tzinfo=MSK)


def test_parse_time_slash_with_time():
    assert parse_time("25/12/2026 09:00") == datetime(2026, 12, 25, 9, 0, tzinfo=MSK)


def test_parse_time_dash_separator():
    assert parse_time("11-04-2026") == datetime(2026, 4, 11, 0, 0, tzinfo=MSK)


def test_parse_time_dash_with_time():
    assert parse_time("25-12-2026 09:00") == datetime(2026, 12, 25, 9, 0, tzinfo=MSK)


def test_parse_time_dash_day_greater_than_12():
    assert parse_time("25-04-2026") == datetime(2026, 4, 25, 0, 0, tzinfo=MSK)


def test_parse_time_invalid():
    """Невалидная дата - 32.13.2026"""
    assert parse_time("32.13.2026") is None


def test_parse_time_returns_aware_datetime():
    result = parse_time("25.12.2026 14:30")

    assert result.tzinfo is not None


def test_parse_time_uses_given_offset():
    result = parse_time("25.12.2026 14:30", 5)

    assert result == datetime(2026, 12, 25, 14, 30, tzinfo=UTC5)
    assert result == datetime(2026, 12, 25, 9, 30, tzinfo=UTC)


def test_parse_time_relative_is_counted_from_now():
    expected = datetime.now(UTC) + timedelta(hours=2)

    result = parse_time("in 2 hours", 5)

    assert abs(result - expected) < timedelta(seconds=5)


def test_parse_time_relative_russian():
    expected = datetime.now(UTC) + timedelta(minutes=30)

    result = parse_time("через 30 минут", -7)

    assert abs(result - expected) < timedelta(seconds=5)


def test_parse_time_clock_time_uses_users_wall_clock():
    """Время без даты берётся по часам пользователя, а не по часам сервера."""
    result = parse_time("tomorrow at 9am", 5)

    assert (result.hour, result.minute) == (9, 0)
    assert result.utcoffset() == timedelta(hours=5)


@pytest.mark.parametrize("text", ["", "   ", "не время вообще"])
def test_parse_time_garbage_returns_none(text):
    assert parse_time(text) is None
