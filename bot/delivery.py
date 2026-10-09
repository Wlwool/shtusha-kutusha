"""Доставка напоминаний в Discord."""

from __future__ import annotations

import datetime
import logging

import discord

from bot.database import delete_reminder, get_reminder

logger = logging.getLogger(__name__)

# Напоминание считается опоздавшим, если оно отправлено позже этого срока.
LATE_AFTER = datetime.timedelta(minutes=1)


def _build_text(
    mention: str, message: str, scheduled: datetime.datetime, now: datetime.datetime
) -> str:
    text = f"{mention}, Вы просили напомнить: {message}"
    if now - scheduled > LATE_AFTER:
        text += (
            f"\n(Напоминание опоздало: оно было назначено на "
            f"{scheduled:%d-%m-%Y %H:%M}, но бот в это время был недоступен.)"
        )
    return text


async def deliver_reminder(
    bot: discord.Client,
    user_id: int,
    channel_id: int,
    message: str,
    reminder_id: int,
    version: int,
) -> None:
    """Отправить напоминание и удалить его из базы.

    Устаревшие задачи (напоминание удалено или изменено) пропускаются.
    Если канал или пользователь удалены, напоминание доставить нельзя:
    оно пишется в лог и удаляется. При других ошибках отправки напоминание
    остаётся в базе и будет отправлено при следующем запуске бота.
    """
    try:
        reminder = await get_reminder(reminder_id)
        if reminder is None:
            logger.info("Напоминание %d уже удалено, пропуск", reminder_id)
            return
        if reminder.version != version:
            logger.info(
                "Напоминание %d: версия задачи %d устарела (в базе %d), пропуск",
                reminder_id,
                version,
                reminder.version,
            )
            return

        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        except discord.NotFound:
            logger.warning(
                "Напоминание %d удалено: канал %d или пользователь %d не найдены. "
                "Текст напоминания: %s",
                reminder_id,
                channel_id,
                user_id,
                message,
            )
            await delete_reminder(reminder_id)
            return

        text = _build_text(
            user.mention, message, reminder.reminder_time, datetime.datetime.now()
        )
        await channel.send(text)
        await delete_reminder(reminder_id)
        logger.info("Отправлено напоминание %d пользователю %d", reminder_id, user_id)
    except Exception:
        logger.exception("Ошибка отправки напоминания %d", reminder_id)
