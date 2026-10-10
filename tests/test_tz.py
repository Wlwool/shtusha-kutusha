"""Тесты вспомогательных функций часовых поясов (bot.tz)"""
import datetime

import pytest

from bot import tz


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("+5", 5),
        ("5", 5),
        ("-3", -3),
        ("0", 0),
        ("-0", 0),
        ("+03", 3),
        (" +14 ", 14),
        ("-12", -12),
    ],
)
def test_parse_utc_offset_valid(text, expected):
    assert tz.parse_utc_offset(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", " ", "abc", "+15", "-13", "100", "5.5", "5,5", "UTC+5", "+", "--5", "٥", "5 5"],
)
def test_parse_utc_offset_invalid(text):
    assert tz.parse_utc_offset(text) is None


def test_format_utc_offset():
    assert tz.format_utc_offset(3) == "UTC+3"
    assert tz.format_utc_offset(-5) == "UTC-5"
    assert tz.format_utc_offset(0) == "UTC+0"


def test_format_local_converts_from_utc():
    moment = datetime.datetime(2026, 12, 25, 12, 0, tzinfo=datetime.UTC)

    assert tz.format_local(moment, 5) == "25-12-2026 17:00"
    assert tz.format_local(moment, -5) == "25-12-2026 07:00"


def test_format_local_crosses_midnight():
    moment = datetime.datetime(2026, 12, 25, 22, 30, tzinfo=datetime.UTC)

    assert tz.format_local(moment, 3) == "26-12-2026 01:30"


def test_offset_to_tz():
    assert tz.offset_to_tz(5).utcoffset(None) == datetime.timedelta(hours=5)


def test_default_offset_is_moscow():
    assert tz.DEFAULT_UTC_OFFSET == 3
