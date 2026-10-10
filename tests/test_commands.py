"""Тесты команд /timezone и /remind, списка и редактирования напоминаний."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands

from bot.cogs.reminders import RemindersCog
from bot.database import (
    Reminder,
    add_reminder,
    get_reminder,
    get_saved_utc_offset,
    get_user_reminders,
    set_utc_offset,
)
from bot.ui.reminder_view import EditReminderModal, ReminderListView

UTC = datetime.UTC


@pytest.fixture
async def fake_bot():
    scheduler = AsyncIOScheduler()
    scheduler.start()
    yield SimpleNamespace(scheduler=scheduler, send_reminder=AsyncMock())
    scheduler.shutdown(wait=False)


@pytest.fixture
def ctx():
    return SimpleNamespace(
        author=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
        send=AsyncMock(),
    )


def _sent_text(ctx) -> str:
    return ctx.send.await_args.args[0]


# /timezone


async def test_timezone_command_is_registered_with_hint():
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
    await bot.add_cog(RemindersCog(bot))

    command = bot.tree.get_command("timezone")

    assert command is not None
    (param,) = command.parameters
    assert param.name == "offset"
    assert param.required is False
    assert "+5" in param.description


async def test_timezone_saves_valid_offset(fake_bot, ctx):
    cog = RemindersCog(fake_bot)

    await cog.timezone.callback(cog, ctx, "+5")

    assert await get_saved_utc_offset(1) == 5
    assert "UTC+5" in _sent_text(ctx)


@pytest.mark.parametrize("text", ["abc", "+15", "-13", "5.5", "UTC+5"])
async def test_timezone_rejects_invalid_offset(fake_bot, ctx, text):
    cog = RemindersCog(fake_bot)

    await cog.timezone.callback(cog, ctx, text)

    assert await get_saved_utc_offset(1) is None
    sent = _sent_text(ctx)
    assert "/timezone" in sent
    assert "-12" in sent
    assert "14" in sent


async def test_timezone_without_argument_shows_default(fake_bot, ctx):
    cog = RemindersCog(fake_bot)

    await cog.timezone.callback(cog, ctx, "")

    sent = _sent_text(ctx)
    assert "UTC+3" in sent
    assert "/timezone" in sent
    assert await get_saved_utc_offset(1) is None


async def test_timezone_without_argument_shows_saved_value(fake_bot, ctx):
    await set_utc_offset(1, -4)
    cog = RemindersCog(fake_bot)

    await cog.timezone.callback(cog, ctx, "")

    assert "UTC-4" in _sent_text(ctx)


# /remind


async def test_remind_uses_users_timezone(fake_bot, ctx):
    await set_utc_offset(1, 5)
    cog = RemindersCog(fake_bot)

    await cog.remind.callback(cog, ctx, "25.12.2030 14:30", message="Позвонить")

    (reminder,) = (await get_user_reminders(1))[0]
    assert reminder.reminder_time == datetime.datetime(2030, 12, 25, 9, 30, tzinfo=UTC)
    job = fake_bot.scheduler.get_job(str(reminder.id))
    assert job.next_run_time == reminder.reminder_time
    sent = _sent_text(ctx)
    assert "25-12-2030 14:30" in sent
    assert "UTC+5" in sent


async def test_remind_shows_timezone_hint_until_user_chooses(fake_bot, ctx):
    cog = RemindersCog(fake_bot)

    await cog.remind.callback(cog, ctx, "25.12.2030 14:30", message="Позвонить")
    first = _sent_text(ctx)
    await set_utc_offset(1, 3)
    await cog.remind.callback(cog, ctx, "26.12.2030 14:30", message="Позвонить")
    second = _sent_text(ctx)

    assert "UTC+3" in first
    assert "/timezone" in first
    assert "UTC+3" in second
    assert "/timezone" not in second


async def test_remind_rejects_past_time_in_users_timezone(fake_bot, ctx):
    await set_utc_offset(1, 14)
    cog = RemindersCog(fake_bot)

    await cog.remind.callback(cog, ctx, "01.01.2020 10:00", message="давно")

    assert (await get_user_reminders(1))[1] == 0
    assert fake_bot.scheduler.get_jobs() == []


# список и редактирование


def _reminder(moment: datetime.datetime) -> Reminder:
    return Reminder(
        id=7,
        user_id=1,
        channel_id=10,
        reminder_time=moment,
        message="Встреча",
        created_at=moment,
        version=1,
    )


async def test_list_embed_shows_time_in_users_timezone(fake_bot):
    moment = datetime.datetime(2030, 12, 25, 12, 0, tzinfo=UTC)
    view = ReminderListView(fake_bot, 1, [_reminder(moment)], 1, 0, utc_offset=5)

    embed = view._build_embed()

    assert "25-12-2030 17:00" in embed.fields[0].name
    assert "UTC+5" in embed.footer.text
    assert "/timezone" in embed.footer.text


async def test_edit_modal_parses_time_in_users_timezone(fake_bot):
    reminder_id = await add_reminder(
        1, 10, datetime.datetime.now(UTC) + datetime.timedelta(hours=1), "Старое"
    )
    reminder = await get_reminder(reminder_id)
    view = ReminderListView(fake_bot, 1, [reminder], 1, 0, utc_offset=5)
    modal = EditReminderModal(
        bot=fake_bot,
        reminder_id=reminder_id,
        current_time="",
        current_message="Старое",
        view=view,
    )
    modal.time_input._value = "25.12.2030 14:30"
    modal.message_input._value = "Новое"
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
        response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()),
    )

    await modal.on_submit(interaction)

    updated = await get_reminder(reminder_id)
    assert updated.reminder_time == datetime.datetime(2030, 12, 25, 9, 30, tzinfo=UTC)
    assert updated.message == "Новое"
    interaction.response.send_message.assert_not_awaited()
    job = fake_bot.scheduler.get_job(str(reminder_id))
    assert job.next_run_time == updated.reminder_time
