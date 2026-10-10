"""Тесты доставки напоминаний: bot.delivery.deliver_reminder."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from bot import delivery
from bot.database import add_reminder, get_reminder, set_utc_offset


def _http_error(cls: type[discord.HTTPException], status: int) -> discord.HTTPException:
    return cls(SimpleNamespace(status=status, reason="test"), "test error")


@pytest.fixture
def channel():
    return SimpleNamespace(send=AsyncMock())


@pytest.fixture
def user():
    return SimpleNamespace(mention="<@1>", send=AsyncMock())


@pytest.fixture
def fake_bot(channel, user):
    """Бот, у которого каналы и пользователи есть в кэше."""
    return SimpleNamespace(
        get_channel=Mock(return_value=channel),
        get_user=Mock(return_value=user),
        fetch_channel=AsyncMock(),
        fetch_user=AsyncMock(),
    )


async def _add(minutes_ago: float, message: str = "Позвонить") -> int:
    when = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=minutes_ago)
    return await add_reminder(1, 10, when, message)


async def test_deliver_sends_message_and_deletes_reminder(fake_bot, channel, user):
    rid = await _add(minutes_ago=0)

    await delivery.deliver_reminder(fake_bot, 1, 10, "Позвонить", rid, 1)

    channel.send.assert_awaited_once()
    user.send.assert_not_awaited()
    text = channel.send.await_args.args[0]
    assert "<@1>" in text
    assert "Позвонить" in text
    assert "опозд" not in text.lower()
    assert await get_reminder(rid) is None


async def test_deliver_skips_deleted_reminder(fake_bot, channel):
    await delivery.deliver_reminder(fake_bot, 1, 10, "msg", 99999, 1)

    channel.send.assert_not_awaited()


async def test_deliver_skips_stale_version(fake_bot, channel):
    rid = await _add(minutes_ago=0)

    await delivery.deliver_reminder(fake_bot, 1, 10, "msg", rid, 5)

    channel.send.assert_not_awaited()
    assert await get_reminder(rid) is not None


async def test_deliver_sends_late_reminder_to_dm(fake_bot, channel, user):
    rid = await _add(minutes_ago=10, message="Встреча")

    await delivery.deliver_reminder(fake_bot, 1, 10, "Встреча", rid, 1)

    user.send.assert_awaited_once()
    channel.send.assert_not_awaited()
    text = user.send.await_args.args[0]
    assert "Встреча" in text
    assert "опозд" in text.lower()
    assert await get_reminder(rid) is None


async def test_deliver_late_reminder_falls_back_to_channel(fake_bot, channel, user):
    user.send.side_effect = _http_error(discord.Forbidden, 403)
    rid = await _add(minutes_ago=10, message="Встреча")

    await delivery.deliver_reminder(fake_bot, 1, 10, "Встреча", rid, 1)

    user.send.assert_awaited_once()
    channel.send.assert_awaited_once()
    text = channel.send.await_args.args[0]
    assert "Встреча" in text
    assert "опозд" in text.lower()
    assert await get_reminder(rid) is None


async def test_deliver_late_reminder_reaches_dm_even_if_channel_is_gone(
    fake_bot, channel, user
):
    fake_bot.get_channel.return_value = None
    fake_bot.fetch_channel.side_effect = _http_error(discord.NotFound, 404)
    rid = await _add(minutes_ago=10)

    await delivery.deliver_reminder(fake_bot, 1, 10, "Позвонить", rid, 1)

    user.send.assert_awaited_once()
    assert await get_reminder(rid) is None


async def test_deliver_uses_fetch_when_cache_is_empty(fake_bot, channel, user):
    fake_bot.get_channel.return_value = None
    fake_bot.get_user.return_value = None
    fake_bot.fetch_channel.return_value = channel
    fake_bot.fetch_user.return_value = user
    rid = await _add(minutes_ago=0)

    await delivery.deliver_reminder(fake_bot, 1, 10, "Позвонить", rid, 1)

    fake_bot.fetch_channel.assert_awaited_once_with(10)
    fake_bot.fetch_user.assert_awaited_once_with(1)
    channel.send.assert_awaited_once()
    assert await get_reminder(rid) is None


async def test_deliver_drops_reminder_when_channel_is_gone(fake_bot, channel):
    fake_bot.get_channel.return_value = None
    fake_bot.fetch_channel.side_effect = _http_error(discord.NotFound, 404)
    rid = await _add(minutes_ago=0)

    await delivery.deliver_reminder(fake_bot, 1, 10, "Позвонить", rid, 1)

    channel.send.assert_not_awaited()
    assert await get_reminder(rid) is None


async def test_deliver_keeps_reminder_when_send_is_forbidden(fake_bot, channel):
    channel.send.side_effect = _http_error(discord.Forbidden, 403)
    rid = await _add(minutes_ago=0)

    await delivery.deliver_reminder(fake_bot, 1, 10, "Позвонить", rid, 1)

    assert await get_reminder(rid) is not None


async def test_late_note_shows_time_in_users_timezone(fake_bot, user):
    await set_utc_offset(1, 5)
    scheduled = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10)
    rid = await add_reminder(1, 10, scheduled, "Встреча")
    expected = scheduled.astimezone(datetime.timezone(datetime.timedelta(hours=5)))

    await delivery.deliver_reminder(fake_bot, 1, 10, "Встреча", rid, 1)

    text = user.send.await_args.args[0]
    assert f"{expected:%d-%m-%Y %H:%M}" in text
    assert "UTC+5" in text


async def test_late_note_uses_moscow_by_default(fake_bot, user):
    scheduled = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10)
    rid = await add_reminder(1, 10, scheduled, "Встреча")
    expected = scheduled.astimezone(datetime.timezone(datetime.timedelta(hours=3)))

    await delivery.deliver_reminder(fake_bot, 1, 10, "Встреча", rid, 1)

    text = user.send.await_args.args[0]
    assert f"{expected:%d-%m-%Y %H:%M}" in text
    assert "UTC+3" in text
